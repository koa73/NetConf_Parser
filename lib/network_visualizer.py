"""
Модуль визуализации сетевой топологии для draw.io
"""
import sys
from pathlib import Path
from typing import Dict, Any, Set, Tuple
import yaml


class NetworkVisualizer:
    """
    Класс для генерации сетевых диаграмм в формате draw.io.
    
    Инициализация с параметрами путей позволяет гибко настраивать расположение шаблонов.
    """

    def __init__(
        self,
        pattern_dir,
        drawio_template,
        drawio_stencil_templates
    ):
        """
        Инициализация визуализатора с настройкой путей к ресурсам.
        
        Args:
            pattern_dir (str): Базовый каталог для презентационных материалов
            drawio_template (str): Шаблон DrawIO файла
            drawio_stencil_templates (str): Каталог шаблонов stencils
        """
        self.pattern_dir = Path(pattern_dir).resolve()
        self.drawio_template =  drawio_template
        self.drawio_stencil_templates = Path(drawio_stencil_templates).resolve()
        self.diagram_template = self.load_drawio_template()
        
        # Валидация базового каталога при инициализации
        if not self.pattern_dir.exists() or not self.pattern_dir.is_dir():
            sys.stderr.write(
                f"❌ ОШИБКА: Базовый каталог презентации не найден: {self.pattern_dir}\n"
            )
            sys.exit(1)

    @staticmethod
    def read_yaml_file(filepath: str) -> Dict[str, Any]:
        """
        Статический метод для чтения YAML-файла.
        При ошибке завершает программу с кодом 1.
        
        Args:
            filepath (str): Путь к YAML-файлу
            
        Returns:
            Dict[str, Any]: Содержимое файла в виде словаря
        """
        path = Path(filepath).resolve()

        # Проверка существования файла
        if not path.exists():
            sys.stderr.write(f"❌ ОШИБКА: Файл не найден: {path}\n")
            sys.exit(1)

        # Проверка прав на чтение
        if not path.is_file() or not path.stat().st_size > 0:
            sys.stderr.write(f"❌ ОШИБКА: Некорректный файл: {path}\n")
            sys.exit(1)

        # Проверка расширения
        if path.suffix.lower() not in ('.yaml', '.yml'):
            sys.stderr.write(
                f"❌ ОШИБКА: Ожидается файл с расширением .yaml или .yml, получено: {path.suffix}\n"
            )
            sys.exit(1)

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

                if not content:
                    sys.stderr.write(f"❌ ОШИБКА: Файл пустой: {path}\n")
                    sys.exit(1)

                data = yaml.safe_load(content)

                if data is None:
                    sys.stderr.write(
                        f"❌ ОШИБКА: Файл не содержит данных (только комментарии): {path}\n"
                    )
                    sys.exit(1)

                if not isinstance(data, dict):
                    sys.stderr.write(
                        f"❌ ОШИБКА: Содержимое YAML должно быть словарём, получено: {type(data).__name__}\n"
                    )
                    sys.exit(1)

                return data

        except yaml.YAMLError as e:
            sys.stderr.write(f"❌ ОШИБКА: Синтаксическая ошибка YAML в файле {path}:\n{e}\n")
            sys.exit(1)
        except UnicodeDecodeError:
            sys.stderr.write(
                f"❌ ОШИБКА: Невозможно декодировать файл '{path}' как UTF-8.\n"
                f"Убедитесь, что файл сохранён в кодировке UTF-8.\n"
            )
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(
                f"❌ ОШИБКА: Неожиданная ошибка при чтении {path}:\n{type(e).__name__}: {e}\n"
            )
            sys.exit(1)

    def load_drawio_template(self) -> str:
        """
        Загружает основной шаблон draw.io из файла.
        
        Returns:
            str: Содержимое XML-шаблона
        """

        try:
            with open(self.drawio_template, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                sys.stderr.write(f"❌ ОШИБКА: Шаблон draw.io пустой: {self.drawio_template}\n")
                sys.exit(1)
            
            return content
            
        except Exception as e:
            sys.stderr.write(
                f"❌ ОШИБКА: Не удалось прочитать шаблон draw.io {self. drawio_template}:\n"
                f"{type(e).__name__}: {e}\n"
            )
            sys.exit(1)


    def load_stencil_templates(self, links: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """
        Загружает шаблоны изображений устройств (stencils) для визуализации.

        Поддерживает структуру index.yaml:
            templates:
              VendorName:
                - type1: filename1.xml
                - type2: filename2.xml

        Args:
            links (Dict[str, Any]): Словарь связей с ключом 'physical_links'

        Returns:
            Dict[str, Dict[str, str]]: Вложенный словарь {вендор: {тип: содержимое_шаблона}}
        """
        # === Шаг 1: Проверка каталога шаблонов ===
        if not self.drawio_stencil_templates.exists() or not self.drawio_stencil_templates.is_dir():
            sys.stderr.write(
                f"❌ ОШИБКА: Каталог шаблонов не найден: {self.drawio_stencil_templates}\n"
            )
            sys.exit(1)

        # === Шаг 2: Загрузка индекса шаблонов ===
        index_file = self.drawio_stencil_templates / "index.yaml"
        index_data = self.read_yaml_file(str(index_file))

        if 'templates' not in index_data:
            sys.stderr.write(f"❌ ОШИБКА: В {index_file} отсутствует ключ 'templates'\n")
            sys.exit(1)

        templates_index = index_data['templates']
        if not isinstance(templates_index, dict):
            sys.stderr.write(
                f"❌ ОШИБКА: 'templates' должен быть словарём, получено {type(templates_index).__name__}\n"
            )
            sys.exit(1)

        # === Шаг 3: Нормализация индекса в формат {вендор: {тип: файл}} ===
        normalized_index: Dict[str, Dict[str, str]] = {}

        for vendor_raw, entries in templates_index.items():
            if not isinstance(entries, list):
                sys.stderr.write(
                    f"⚠️  ВНИМАНИЕ: Для вендора '{vendor_raw}' ожидается список, "
                    f"получено {type(entries).__name__}. Пропускаем.\n"
                )
                continue

            vendor_key = vendor_raw.lower()
            normalized_index.setdefault(vendor_key, {})

            for entry in entries:
                if not isinstance(entry, dict) or len(entry) != 1:
                    sys.stderr.write(
                        f"⚠️  ВНИМАНИЕ: Некорректная запись для вендора '{vendor_raw}': {entry}. Пропускаем.\n"
                    )
                    continue

                dev_type, filename = next(iter(entry.items()))
                if not isinstance(dev_type, str) or not isinstance(filename, str):
                    sys.stderr.write(
                        f"⚠️  ВНИМАНИЕ: Некорректный тип/имя файла для '{vendor_raw}': {entry}. Пропускаем.\n"
                    )
                    continue

                normalized_index[vendor_key][dev_type.lower()] = filename

        # === Шаг 4: Извлечение уникальных пар (вендор, тип) из физических связей ===
        physical_links = links.get('physical_links', [])
        if not isinstance(physical_links, list):
            sys.stderr.write(
                f"❌ ОШИБКА: 'physical_links' должен быть списком, "
                f"получено {type(physical_links).__name__}\n"
            )
            sys.exit(1)

        unique_devices: Set[Tuple[str, str]] = {
            ('common', 'network'),
            ('common', 'physical_link'),
            ('common', 'logical_link'),
            ('common', 'mgm_link')
        }

        for link in physical_links:
            # Структура: [dev1, vendor1, type1, intf1, ip1, dev2, vendor2, type2, intf2, ip2, net]
            if len(link) < 11:
                sys.stderr.write(
                    f"❌ ОШИБКА: Некорректная структура связи (длина {len(link)} < 11):\n{link}\n"
                )
                sys.exit(1)

            vendor1 = str(link[1]).lower()
            type1 = str(link[2]).lower()
            vendor2 = str(link[6]).lower()
            type2 = str(link[7]).lower()

            unique_devices.add((vendor1, type1))
            unique_devices.add((vendor2, type2))


        if len(unique_devices) < 5:
            sys.stderr.write(
                "ℹ️  Не обнаружено устройств в физических связях. Возврат пустого словаря шаблонов.\n"
            )
            return {}

        # === Шаг 5: Загрузка шаблонов ===
        templates: Dict[str, Dict[str, str]] = {}
        missing_templates = []

        for vendor, dev_type in sorted(unique_devices):
            vendor_idx = normalized_index.get(vendor)

            if not vendor_idx:
                available_vendors = [v for v in normalized_index.keys() if normalized_index[v]]
                missing_templates.append(
                    f"  • (вендор='{vendor}', тип='{dev_type}'): вендор отсутствует в индексе. "
                    f"Доступные: {', '.join(sorted(available_vendors)) or 'нет'}"
                )
                continue

            filename = vendor_idx.get(dev_type)
            if not filename:
                available_types = list(vendor_idx.keys())
                missing_templates.append(
                    f"  • (вендор='{vendor}', тип='{dev_type}'): шаблон не найден. "
                    f"Доступные типы: {', '.join(sorted(available_types)) or 'нет'}"
                )
                continue

            template_path = self.drawio_stencil_templates / filename
            if not template_path.exists():
                missing_templates.append(
                    f"  • (вендор='{vendor}', тип='{dev_type}'): файл '{filename}' "
                    f"не найден по пути {template_path}"
                )
                continue

            templates.setdefault(vendor, {})[dev_type] = self.read_yaml_file(str(template_path))['xml']

        # === Шаг 6: Отчёт о результатах ===
        total_loaded = sum(len(types) for types in templates.values())
        total_requested = len(unique_devices)

        print(f"   Успешно загружено шаблонов: {total_loaded}\n")

        if missing_templates:
            sys.stderr.write(f"   ❌ Не найдены шаблоны для {len(missing_templates)} комбинаций:\n")
            for msg in missing_templates:
                sys.stderr.write(f"{msg}\n")

        if total_loaded == 0 and total_requested > 0:
            sys.stderr.write(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: Не загружено ни одного шаблона!\n")
            sys.exit(1)

        return templates

    def make_object_list(self, links_result: Dict[str, Any], templates: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        """
        Генерирует список объектов draw.io для визуализации устройств, сетей и связей.

        Args:
            links_result (Dict[str, Any]): Словарь с результатами анализа топологии
            templates (Dict[str, Dict[str, str]]): Словарь шаблонов устройств

        Returns:
            Dict[str, str]: Словарь с объектами draw.io для устройств, сетей и связей
        """
        objects = {
            'devices': {},
            'networks': {},
            'physical_links': {},
            'mgm_links': {},
            'logical_links': {}
        }

        # Получаем физические связи
        physical_links = links_result.get('physical_links', [])

        # Собираем уникальные устройства из физических связей
        devices = set()
        networks = set()

        for link in physical_links:
            # Структура: [dev1, vendor1, type1, intf1, ip1, dev2, vendor2, type2, intf2, ip2, net]
            if len(link) >= 11:
                dev1 = link[0]
                dev2 = link[5]
                network = link[10]

                devices.add(dev1)
                devices.add(dev2)
                networks.add(network)

        # Добавляем управленческие интерфейсы
        mgmt_networks = links_result.get('mgmt_networks', [])
        for mgmt in mgmt_networks:
            if len(mgmt) >= 4:
                dev = mgmt[0]
                network = mgmt[3]
                devices.add(dev)
                networks.add(network)

        # Добавляем логические связи
        logical_links = links_result.get('logical_links', [])
        for logical in logical_links:
            if len(logical) >= 5:
                dev1 = logical[0]
                dev2 = logical[2]
                # Извлекаем сеть из описания
                desc = logical[4]
                if 'Service Network:' in desc:
                    network = desc.split('Service Network:')[1].strip()
                    networks.add(network)

                devices.add(dev1)
                devices.add(dev2)

        # Создаем объекты для устройств
        for device in devices:
            # Для каждого устройства нужно определить его вендора и тип
            # Находим информацию об устройстве в физических связях
            vendor = "unknown"
            dev_type = "unknown"

            # Ищем информацию об устройстве в физических связях
            for link in physical_links:
                if len(link) >= 8 and (link[0] == device or link[5] == device):
                    if link[0] == device:
                        vendor = link[1].lower()
                        dev_type = link[2].lower()
                    elif link[5] == device:
                        vendor = link[6].lower()
                        dev_type = link[7].lower()
                    break

            # Если не нашли в физических связях, ищем в управленческих
            if vendor == "unknown" or dev_type == "unknown":
                for mgmt in mgmt_networks:
                    if len(mgmt) >= 1 and mgmt[0] == device:
                        # В данном случае не можем точно определить vendor и type
                        # используем информацию из других источников
                        break

            # Пытаемся получить шаблон для устройства
            vendor_templates = templates.get(vendor, {})
            device_template = vendor_templates.get(dev_type)

            if device_template:
                # Заменяем --NAME-- на имя устройства
                device_xml = device_template.replace('--NAME--', device)
                objects['devices'][device] = device_xml
            else:
                # Используем шаблон по умолчанию
                default_template = vendor_templates.get('default') or templates.get('common', {}).get('default')
                if default_template:
                    device_xml = default_template.replace('--NAME--', device)
                    objects['devices'][device] = device_xml

        # Создаем объекты для сетей
        for network in networks:
            # Используем шаблон сети
            network_template = templates.get('common', {}).get('network')
            if network_template:
                # Заменяем --NAME-- на адрес сети
                network_xml = network_template.replace('--NAME--', network)
                objects['networks'][network] = network_xml

        # Создаем объекты для физических связей
        for i, link in enumerate(physical_links):
            if len(link) >= 11:
                dev1 = link[0]
                dev2 = link[5]
                network = link[10]

                # Используем шаблон физической связи
                link_template = templates.get('common', {}).get('physical_link')
                if link_template:
                    # Заменяем --NAME-- на информацию о связи
                    link_xml = link_template.replace('--NAME--', f"{dev1}-{dev2}")
                    objects['physical_links'][f"link_{i}_{dev1}_{dev2}"] = link_xml

        # Создаем объекты для управленческих связей
        mgmt_networks = links_result.get('mgmt_networks', [])
        for i, mgmt in enumerate(mgmt_networks):
            if len(mgmt) >= 4:
                dev = mgmt[0]
                interface = mgmt[1] if len(mgmt) > 1 else "unknown"
                ip = mgmt[2] if len(mgmt) > 2 else "unknown"
                network = mgmt[3] if len(mgmt) > 3 else "unknown"

                # Используем шаблон управленческой связи
                mgm_link_template = templates.get('common', {}).get('mgm_link')
                if mgm_link_template:
                    # Заменяем --NAME-- на информацию о связи
                    mgm_link_xml = mgm_link_template.replace('--NAME--', f"{dev}:{interface}")
                    objects['mgm_links'][f"mgm_link_{i}_{dev}"] = mgm_link_xml

        # Создаем объекты для логических связей
        logical_links = links_result.get('logical_links', [])
        for i, logical in enumerate(logical_links):
            if len(logical) >= 5:
                dev1 = logical[0]
                dev2 = logical[2]
                desc = logical[4]

                # Используем шаблон логической связи
                logical_link_template = templates.get('common', {}).get('logical_link')
                if logical_link_template:
                    # Заменяем --NAME-- на информацию о связи
                    logical_link_xml = logical_link_template.replace('--NAME--', f"{dev1}-{dev2}({desc})")
                    objects['logical_links'][f"logical_link_{i}_{dev1}_{dev2}"] = logical_link_xml

        return objects
