# visualizer.py

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Set, Tuple

PRESENTATION_DIR = "../presentation"
TEMPLATES_DIR = os.path.join(PRESENTATION_DIR, "templates")
DRAWIO_TEMPLATE = "drawio_template.xml"


def read_yaml_file(filepath: str) -> Dict[str, Any]:
    """
    Считывает YAML-файл и возвращает его содержимое в виде словаря.

    Args:
        filepath (str): Путь к YAML-файлу (абсолютный или относительный).

    Returns:
        Dict[str, Any]: Содержимое YAML-файла в виде словаря.
    """

    path = Path(filepath).resolve()

    # Проверка существования файла
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    # Проверка прав на чтение
    if not os.access(path, os.R_OK):
        raise PermissionError(f"Нет прав на чтение файла: {path}")

    # Проверка расширения (опционально)
    if path.suffix.lower() not in ('.yaml', '.yml'):
        raise ValueError(f"Ожидается файл с расширением .yaml или .yml, получено: {path.suffix}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

            if not content:
                raise ValueError(f"Файл пустой: {path}")

            data = yaml.safe_load(content)

            if data is None:
                raise ValueError(f"Файл не содержит данных или состоит только из комментариев: {path}")

            if not isinstance(data, dict):
                raise TypeError(f"Содержимое YAML должно быть словарём (dict), получено: {type(data).__name__}")

            return data

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Ошибка синтаксиса YAML в файле {path}:\n{str(e)}") from e
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            "utf-8", b"", 0, 1,
            f"Ошибка декодирования UTF-8 в файле {path}. Убедитесь, что файл сохранён в кодировке UTF-8."
        ) from e

def load_drawio_template() -> str:
    """Загружает шаблон XML для draw.io из файла"""
    template_path = os.path.join(PRESENTATION_DIR, DRAWIO_TEMPLATE )
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(
            f"❌ Файл шаблона draw.io не найден: {template_path}\n"
            f"💡 Пожалуйста, создайте файл шаблона или скопируйте пример из документации"
        )
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        raise Exception(f"❌ Ошибка чтения шаблона draw.io: {str(e)}")

def load_stencil_templates(stencil_dir: str, links: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Загружает шаблоны изображений устройств (stencils) для визуализации сетевой диаграммы.

    Анализирует физические связи, извлекает уникальные пары (вендор, тип устройства)
    и загружает соответствующие шаблоны из каталога на основе индекса index.yaml.

    Args:
        stencil_dir (str): Путь к каталогу с шаблонами (stencil templates).
        links (Dict[str, Any]): Словарь связей, должен содержать ключ 'physical_links'.

    Returns:
        Dict[str, Dict[str, str]]: Вложенный словарь шаблонов вида:
            {
                'cisco': {
                    'router': '<mxgraph...>...</mxgraph>',
                    'switch': '<mxgraph...>...</mxgraph>'
                },
                'huawei': {
                    'switch': '<mxgraph...>...</mxgraph>'
                },
                ...
            }

    Программа завершается с кодом 1 при любой ошибке.
    """
    stencil_path = Path(stencil_dir).resolve()

    # === Шаг 1: Проверка существования каталога шаблонов ===
    if not stencil_path.exists():
        sys.stderr.write(f"❌ ОШИБКА: Каталог шаблонов не найден: {stencil_path}\n")
        sys.exit(1)

    if not stencil_path.is_dir():
        sys.stderr.write(f"❌ ОШИБКА: Указанный путь не является каталогом: {stencil_path}\n")
        sys.exit(1)

    # === Шаг 2: Загрузка индекса шаблонов ===
    index_file = stencil_path / "index.yaml"
    if not index_file.exists():
        sys.stderr.write(f"❌ ОШИБКА: Файл индекса не найден: {index_file}\n")
        sys.exit(1)

    try:
        index_data = read_yaml_file(str(index_file))
    except Exception as e:
        # read_yaml_file уже завершает программу при ошибке, но на случай импорта:
        sys.stderr.write(f"❌ ОШИБКА: Не удалось загрузить индекс шаблонов {index_file}:\n{e}\n")
        sys.exit(1)

    # Валидация структуры индекса
    if 'templates' not in index_data:
        sys.stderr.write(f"❌ ОШИБКА: В файле {index_file} отсутствует ключ 'templates'\n")
        sys.exit(1)

    templates_index = index_data['templates']
    if not isinstance(templates_index, dict):
        sys.stderr.write(
            f"❌ ОШИБКА: Ключ 'templates' должен быть словарём, получено: {type(templates_index).__name__}\n")
        sys.exit(1)

    # === Шаг 3: Извлечение уникальных пар (вендор, тип) из физических связей ===
    physical_links = links.get('physical_links', [])

    if not isinstance(physical_links, list):
        sys.stderr.write(f"❌ ОШИБКА: 'physical_links' должен быть списком, получено: {type(physical_links).__name__}\n")
        sys.exit(1)

    unique_devices: Set[Tuple[str, str]] = set()

    for link in physical_links:
        # Ожидаемая структура после модификации find_physical_links:
        # [dev1, vendor1, type1, intf1, ip1, dev2, vendor2, type2, intf2, ip2, net]
        if len(link) < 11:
            sys.stderr.write(
                f"❌ ОШИБКА: Некорректная структура связи (ожидается 11+ элементов, получено {len(link)}):\n{link}\n"
            )
            sys.exit(1)

        # Устройство 1
        vendor1 = link[1].lower() if isinstance(link[1], str) else str(link[1]).lower()
        type1 = link[2].lower() if isinstance(link[2], str) else str(link[2]).lower()
        unique_devices.add((vendor1, type1))

        # Устройство 2
        vendor2 = link[6].lower() if isinstance(link[6], str) else str(link[6]).lower()
        type2 = link[7].lower() if isinstance(link[7], str) else str(link[7]).lower()
        unique_devices.add((vendor2, type2))

    if not unique_devices:
        sys.stderr.write(
            "⚠️  ВНИМАНИЕ: Не обнаружено уникальных устройств в физических связях. Возврат пустого словаря шаблонов.\n")
        return {}

    # === Шаг 4: Загрузка шаблонов для каждой уникальной пары (вендор, тип) ===
    templates: Dict[str, Dict[str, str]] = {}

    for vendor, device_type in sorted(unique_devices):
        # Поиск шаблона в индексе
        vendor_templates = templates_index.get(vendor, {})
        if not isinstance(vendor_templates, dict):
            sys.stderr.write(
                f"❌ ОШИБКА: Для вендора '{vendor}' ожидается словарь шаблонов, получено: {type(vendor_templates).__name__}\n"
            )
            sys.exit(1)

        template_filename = vendor_templates.get(device_type)
        if not template_filename:
            sys.stderr.write(
                f"⚠️  ВНИМАНИЕ: Шаблон не найден для комбинации (вендор='{vendor}', тип='{device_type}') в {index_file}\n"
                f"    Доступные типы для '{vendor}': {list(vendor_templates.keys()) if vendor_templates else 'нет'}\n"
            )
            continue  # Пропускаем отсутствующий шаблон, продолжаем обработку

        # Загрузка файла шаблона
        template_path = stencil_path / template_filename

        if not template_path.exists():
            sys.stderr.write(
                f"❌ ОШИБКА: Файл шаблона не найден: {template_path}\n"
                f"    Указано в индексе для (вендор='{vendor}', тип='{device_type}'): {template_filename}\n"
            )
            sys.exit(1)

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read().strip()

            if not template_content:
                sys.stderr.write(f"⚠️  ВНИМАНИЕ: Шаблон пустой: {template_path}\n")
                template_content = "<!-- Пустой шаблон -->"

            # Сохранение в иерархический словарь
            templates.setdefault(vendor, {})[device_type] = template_content

        except UnicodeDecodeError:
            sys.stderr.write(
                f"❌ ОШИБКА: Невозможно декодировать шаблон как UTF-8: {template_path}\n"
                f"    Убедитесь, что файл сохранён в кодировке UTF-8.\n"
            )
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(f"❌ ОШИБКА: Не удалось прочитать шаблон {template_path}:\n{type(e).__name__}: {e}\n")
            sys.exit(1)

    # === Шаг 5: Отчёт о результатах ===
    total_loaded = sum(len(types) for types in templates.values())
    sys.stderr.write(
        f"✅ Загружено шаблонов: {total_loaded} "
        f"(уникальных комбинаций вендор/тип: {len(unique_devices)}, "
        f"найдено в индексе: {total_loaded})\n"
    )

    return templates