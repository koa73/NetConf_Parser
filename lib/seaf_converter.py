"""
SEAF Converter - модуль для работы с YAML схемами SEAF.

Предоставляет объектно-ориентированный интерфейс для парсинга,
обработки и формирования словарей на основе YAML схем.
"""

import re
from pathlib import Path
from typing import Any

import yaml


class SchemaLoader:
    """Загрузчик YAML схем из указанного каталога."""

    def __init__(self, patterns_dir: str | Path) -> None:
        self.patterns_dir = Path(patterns_dir)
        self._schemas: dict[str, dict[str, Any]] = {}
        self._entities: dict[str, dict[str, Any]] = {}

    def load_all_schemas(self) -> dict[str, dict[str, Any]]:
        """Загрузить все YAML файлы из каталога схем."""
        if not self.patterns_dir.exists():
            raise FileNotFoundError(f"Каталог схем не найден: {self.patterns_dir}")

        yaml_files = list(self.patterns_dir.glob("*.yaml"))

        for yaml_file in yaml_files:
            schema_data = self._load_yaml_file(yaml_file)
            if schema_data:
                self._schemas[yaml_file.stem] = schema_data
                self._extract_entities(schema_data)

        return self._schemas

    def _extract_entities(self, schema_data: dict[str, Any]) -> None:
        """Извлечь сущности из структуры entities."""
        entities = schema_data.get("entities", {})
        for entity_name, entity_data in entities.items():
            self._entities[entity_name] = entity_data

    def _load_yaml_file(self, file_path: Path) -> dict[str, Any] | None:
        """Загрузить отдельный YAML файл."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Ошибка парсинга YAML файла {file_path}: {e}")

    def get_schema(self, name: str) -> dict[str, Any] | None:
        """Получить схему по имени файла."""
        return self._schemas.get(name)

    @property
    def schemas(self) -> dict[str, dict[str, Any]]:
        """Вернуть все загруженные схемы."""
        return self._schemas

    @property
    def entities(self) -> dict[str, dict[str, Any]]:
        """Вернуть все извлечённые сущности."""
        return self._entities


class SchemaResolver:
    """Резольвер схем - обрабатывает наследование и ссылки между схемами."""

    def __init__(
        self,
        schemas: dict[str, dict[str, Any]],
        entities: dict[str, dict[str, Any]],
    ) -> None:
        self.schemas = schemas
        self.entities = entities
        self._base_entities: dict[str, Any] = {}
        self._resolved_schemas: dict[str, dict[str, Any]] = {}

    @property
    def resolved_schemas(self) -> dict[str, dict[str, Any]]:
        """Вернуть все разрешённые схемы."""
        return self._resolved_schemas

    def resolve_all(self) -> dict[str, dict[str, Any]]:
        """Разрешить все ссылки и наследование в схемах."""
        self._extract_base_entities()

        for entity_name, entity_data in self.entities.items():
            schema_data = entity_data.get("schema", {})
            if schema_data:
                resolved = self._resolve_entity_schema(entity_name, schema_data)
                self._resolved_schemas[entity_name] = resolved

        return self._resolved_schemas

    def _extract_base_entities(self) -> None:
        """Извлечь базовые сущности из base_entity.yaml."""
        base_schema = self.schemas.get("base_entity")
        if not base_schema:
            return

        entities = base_schema.get("entities", {})
        for entity_name, entity_data in entities.items():
            schema_part = entity_data.get("schema", {})
            defs = schema_part.get("$defs", {})
            self._base_entities.update(defs)

    def _resolve_entity_schema(
        self, entity_name: str, schema_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Разрешить схему сущности, объединив с базовыми сущностями."""
        resolved = schema_data.copy()

        pattern_props = resolved.get("patternProperties", {})

        for pattern, pattern_def in pattern_props.items():
            resolved_pattern = self._resolve_pattern_definition(pattern_def)
            pattern_props[pattern] = resolved_pattern

        return resolved

    def _resolve_pattern_definition(
        self, pattern_def: dict[str, Any]
    ) -> dict[str, Any]:
        """Разрешить определение patternProperties с учётом allOf/oneOf."""
        resolved = pattern_def.copy()

        all_of = pattern_def.get("allOf", [])
        one_of = pattern_def.get("oneOf", [])

        resolved_all_of = []
        for ref_item in all_of:
            if "$ref" in ref_item:
                base_entity = self._resolve_reference(ref_item["$ref"])
                if base_entity:
                    resolved_all_of.append(base_entity)
            else:
                resolved_all_of.append(ref_item)

        resolved_one_of = []
        for ref_item in one_of:
            if "$ref" in ref_item:
                variant = self._resolve_reference(ref_item["$ref"])
                if variant:
                    resolved_one_of.append(variant)
            else:
                resolved_one_of.append(ref_item)

        if resolved_all_of:
            resolved["allOf"] = resolved_all_of
        if resolved_one_of:
            resolved["oneOf"] = resolved_one_of

        return resolved

    def _resolve_reference(self, ref: str) -> dict[str, Any] | None:
        """Разрешить ссылку вида #/$defs/... или #/$defs/.../..."""
        if not ref.startswith("#/$defs/"):
            return None

        path = ref.replace("#/$defs/", "")
        parts = path.split("/")

        # Сначала ищем в базовых сущностях (простой ключ)
        if len(parts) == 1:
            return self._base_entities.get(parts[0])

        # Сложный путь: ищем в $defs схем сущностей
        # Путь вида: seaf.company.ta.services.networks/wan
        # Ищем в schema.$defs каждой сущности
        for entity_name, entity_data in self.entities.items():
            schema_data = entity_data.get("schema", {})
            defs = schema_data.get("$defs", {})

            # Первый элемент пути - имя defs
            defs_name = parts[0]
            if defs_name in defs:
                def_data = defs[defs_name]

                # Если есть дополнительные части пути (например, /wan)
                if len(parts) > 1:
                    # def_data может быть dict с вложенными ключами
                    if isinstance(def_data, dict):
                        current = def_data
                        for part in parts[1:]:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                current = None
                                break
                        if current and isinstance(current, dict):
                            return current
                else:
                    if isinstance(def_data, dict):
                        return def_data

        # Если не нашли, ищем в базовых сущностях по составному пути
        if len(parts) > 1:
            base_name = parts[0]
            if base_name in self._base_entities:
                base_data = self._base_entities[base_name]
                if isinstance(base_data, dict):
                    current = base_data
                    for part in parts[1:]:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            return None
                    return current if isinstance(current, dict) else None

        return None


class SchemaDictionaryBuilder:
    """Билдер для формирования финального словаря схем."""

    def __init__(
        self,
        resolved_schemas: dict[str, dict[str, Any]],
        entities: dict[str, dict[str, Any]],
    ) -> None:
        self.resolved_schemas = resolved_schemas
        self.entities = entities

    def build(self) -> dict[str, Any]:
        """Построить финальный словарь схем."""
        result: dict[str, Any] = {}

        for entity_name, schema_data in self.resolved_schemas.items():
            objects = self._get_objects_for_entity(entity_name)

            for object_name in objects:
                pattern_props = schema_data.get("patternProperties", {})

                for pattern, pattern_def in pattern_props.items():
                    variants = self._extract_variants(pattern_def)
                    if variants:
                        # Если есть варианты (LAN/WAN), добавляем их
                        result[object_name] = variants
                    elif pattern_def.get("properties"):
                        # Если свойства определены напрямую (без oneOf)
                        result[object_name] = self._build_direct_template(pattern_def)

        return result

    def _get_objects_for_entity(self, entity_name: str) -> list[str]:
        """Получить имена объектов для сущности."""
        entity_data = self.entities.get(entity_name, {})
        objects = entity_data.get("objects", {})
        result = []
        for obj_name, obj_data in objects.items():
            if obj_data.get("route") == "/":
                result.append(obj_name)
        return result

    def _extract_variants(self, pattern_def: dict[str, Any]) -> dict[str, Any] | None:
        """Извлечь варианты (LAN/WAN) из oneOf с наследованием из allOf."""
        one_of = pattern_def.get("oneOf", [])

        # Если есть oneOf - обрабатываем варианты (LAN/WAN)
        if one_of:
            return self._extract_oneof_variants(pattern_def, one_of)

        # Если нет oneOf - проверяем наличие properties напрямую
        properties = pattern_def.get("properties", {})
        if properties:
            return self._build_direct_template(pattern_def)

        return None

    def _extract_oneof_variants(
        self, pattern_def: dict[str, Any], one_of: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Извлечь варианты из oneOf с наследованием из allOf."""
        variants = {}
        all_of = pattern_def.get("allOf", [])

        # Получаем базовые свойства из allOf
        base_properties = {}
        base_required = []
        for base_schema in all_of:
            props = base_schema.get("properties", {})
            base_properties.update(props)
            base_required.extend(base_schema.get("required", []))

        for variant_schema in one_of:
            variant_name = self._get_variant_name(variant_schema)
            if variant_name:
                properties = variant_schema.get("properties", {})
                required = variant_schema.get("required", [])

                # Объединяем базовые свойства с свойствами варианта
                merged_properties = {**base_properties, **properties}
                merged_required = base_required + required

                variants[variant_name] = self._build_variant_template(
                    merged_properties, merged_required
                )

        return variants if variants else None

    def _build_direct_template(self, pattern_def: dict[str, Any]) -> dict[str, Any]:
        """Построить шаблон из напрямую определённых properties (без oneOf)."""
        all_of = pattern_def.get("allOf", [])
        properties = pattern_def.get("properties", {})
        required = pattern_def.get("required", [])

        # Получаем базовые свойства из allOf
        base_properties = {}
        for base_schema in all_of:
            props = base_schema.get("properties", {})
            base_properties.update(props)

        # Объединяем базовые свойства с прямыми свойствами
        merged_properties = {**base_properties, **properties}

        template: dict[str, Any] = {}
        for prop_name, prop_def in merged_properties.items():
            default_value = self._get_default_value(prop_def)
            template[prop_name] = default_value

        return template

    def _get_variant_name(self, variant_schema: dict[str, Any]) -> str | None:
        """Определить имя варианта (LAN/WAN) по свойствам."""
        properties = variant_schema.get("properties", {})

        type_prop = properties.get("type", {})
        enum_values = type_prop.get("enum", [])

        if "WAN" in enum_values:
            return "WAN"
        if "LAN" in enum_values:
            return "LAN"

        type_prop_name = properties.get("type", {})
        title = type_prop_name.get("title", "")
        if "WAN" in title:
            return "WAN"
        if "LAN" in title:
            return "LAN"

        return None

    def _build_variant_template(
        self, properties: dict[str, Any], required: list[str]
    ) -> dict[str, Any]:
        """Построить шаблон для варианта с полями."""
        template: dict[str, Any] = {}

        for prop_name, prop_def in properties.items():
            default_value = self._get_default_value(prop_def)
            template[prop_name] = default_value

        return template

    def _build_empty_template(self, pattern_def: dict[str, Any]) -> dict[str, Any]:
        """Построить пустой шаблон из allOf."""
        template: dict[str, Any] = {}
        all_of = pattern_def.get("allOf", [])

        for base_schema in all_of:
            properties = base_schema.get("properties", {})
            for prop_name, prop_def in properties.items():
                if prop_name not in template:
                    template[prop_name] = self._get_default_value(prop_def)

        return template

    def _get_default_value(self, prop_def: dict[str, Any]) -> Any:
        """Определить значение по умолчанию для свойства."""
        prop_type = prop_def.get("type", "string")

        if prop_type == "array":
            return []
        if prop_type == "integer":
            return 0
        if prop_type == "boolean":
            return False
        if "enum" in prop_def:
            # Возвращаем список enum-значений или строку, если значение одно
            enum_values = prop_def.get("enum", [])
            if len(enum_values) == 1:
                return enum_values[0]
            return enum_values if enum_values else None

        return ""


class SeafConverter:
    """
    Основной класс конвертера SEAF схем.

    Предоставляет интерфейс для загрузки, обработки и формирования
    словарей на основе YAML схем из каталога patterns/seaf.
    """

    def __init__(self, patterns_dir: str | Path | None = None) -> None:
        """
        Инициализировать конвертер.

        Args:
            patterns_dir: Путь к каталогу с YAML схемами.
                         По умолчанию: patterns/seaf относительно текущего файла.
        """
        if patterns_dir is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            patterns_dir = project_root / "patterns" / "seaf"

        self.patterns_dir = Path(patterns_dir)
        self._loader: SchemaLoader | None = None
        self._resolver: SchemaResolver | None = None
        self._builder: SchemaDictionaryBuilder | None = None
        self._dictionary: dict[str, Any] | None = None

    def load_schemas(self) -> "SeafConverter":
        """
        Загрузить все схемы из каталога.

        Returns:
            self для цепочки вызовов.
        """
        self._loader = SchemaLoader(self.patterns_dir)
        self._loader.load_all_schemas()
        return self

    def resolve_schemas(self) -> "SeafConverter":
        """
        Разрешить все ссылки и наследование в схемах.

        Returns:
            self для цепочки вызовов.

        Raises:
            ValueError: Если схемы не загружены.
        """
        if not self._loader:
            raise ValueError("Сначала загрузите схемы методом load_schemas()")

        self._resolver = SchemaResolver(
            self._loader.schemas, self._loader.entities
        )
        self._resolver.resolve_all()
        return self

    def build_dictionary(self) -> "SeafConverter":
        """
        Построить финальный словарь схем.

        Returns:
            self для цепочки вызовов.

        Raises:
            ValueError: Если схемы не разрешены.
        """
        if not self._resolver:
            raise ValueError("Сначала разрешите схемы методом resolve_schemas()")

        self._builder = SchemaDictionaryBuilder(
            self._resolver.resolved_schemas, self._loader.entities
        )
        self._dictionary = self._builder.build()
        return self

    def get_seaf_dictionary(self) -> dict[str, Any]:
        """
        Получить словарь SEAF схем.

        Возвращает словарь вида:
        {
            <имя_файла>: {
                "properties": <шаблон свойств>,
                ...
            },
            ...
        }

        Для объектов с вариантами (LAN/WAN):
        {
            "network": {
                "LAN": {<свойства LAN>},
                "WAN": {<свойства WAN>}
            }
        }

        Returns:
            Словарь SEAF схем.

        Raises:
            ValueError: Если словарь не построен.
        """
        if self._dictionary is None:
            self.load_schemas().resolve_schemas().build_dictionary()

        return self._dictionary if self._dictionary else {}

    def get_schema_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Получить схему по имени.

        Args:
            name: Имя схемы (имя файла без расширения).

        Returns:
            Схема или None, если не найдена.
        """
        if not self._loader:
            self.load_schemas()

        return self._loader.get_schema(name) if self._loader else None

    def reload(self) -> "SeafConverter":
        """
        Перезагрузить все схемы и перестроить словарь.

        Returns:
            self для цепочки вызовов.
        """
        self._dictionary = None
        self._loader = None
        self._resolver = None
        self._builder = None
        return self.load_schemas().resolve_schemas().build_dictionary()


def get_seaf_dictionary(patterns_dir: str | Path | None = None) -> dict[str, Any]:
    """
    Получить словарь SEAF схем (функциональный интерфейс).

    Args:
        patterns_dir: Путь к каталогу с YAML схемами.
                     По умолчанию: patterns/seaf проекта.

    Returns:
        Словарь SEAF схем.
    """
    converter = SeafConverter(patterns_dir)
    return converter.get_seaf_dictionary()


if __name__ == "__main__":
    import json

    converter = SeafConverter()
    dictionary = converter.get_seaf_dictionary()
    print(json.dumps(dictionary, ensure_ascii=False, indent=2))
