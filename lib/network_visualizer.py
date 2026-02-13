"""
Модуль визуализации сетевой топологии для draw.io
"""
import sys
from pathlib import Path
from typing import Dict, Any
from N2G import  drawio_diagram
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
        
        # Валидация базового каталога при инициализации
        if not self.pattern_dir.exists() or not self.pattern_dir.is_dir():
            sys.stderr.write(
                f"❌ ОШИБКА: Базовый каталог презентации не найден: {self.pattern_dir}\n"
            )
            sys.exit(1)

    @staticmethod
    def _read_yaml_file(filepath: str) -> Dict[str, Any]:
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

    def merge_yaml_files(self) -> Dict[str, Any]:
        """
        Reads index.yaml file, reads devices.yaml from the same directory,
        and replaces string values in index with corresponding dictionaries from devices.yaml.

        Returns:
            Dictionary with merged data
        """
        directory = Path(self.drawio_stencil_templates)

        # Read the index.yaml file
        with open(directory / 'index.yaml', 'r', encoding='utf-8') as f:
            index_data = yaml.safe_load(f)

        # Read the devices.yaml file from the same directory
        devices_path = directory / 'stencils.yaml'
        if devices_path.exists():
            with open(devices_path, 'r', encoding='utf-8') as f:
                devices_data = yaml.safe_load(f)
        else:
            # If devices.yaml doesn't exist, return the original index data
            return index_data

        # Create a new dictionary with merged data
        result = {}

        # Process each vendor in the index
        for vendor, device_list in index_data.get('templates', {}).items():
            result[vendor] = []

            # Process each device type in the vendor list
            for device_dict in device_list:
                # device_dict is like {"carrier_switch": "switch"}
                for device_type, device_name in device_dict.items():
                    # Get the corresponding device data from devices.yaml
                    device_info = devices_data.get(device_name)

                    if device_info is not None:
                        # Replace the string with the dictionary from devices.yaml
                        result[vendor].append({device_type: device_info})
                    else:
                        # If device name not found in devices.yaml, keep the original
                        result[vendor].append({device_type: device_name})

        return result

    @staticmethod
    def generate_device_list(data: Dict[str, Any], patterns: Dict[str, Any]) -> Dict[str, Any]:
        """
        Процедура формирования списка устройств на основе link_result и merge_yaml_files

        Args:
            data (dict): Словарь с результатами линков, содержащий physical_links и mgmt_networks
            patterns (dict): Словарь шаблонов устройств, где ключи - это вендоры, а значения - списки шаблонов

        Returns:
            dict: Словарь в формате {имя_устройства: {данные_из_шаблона}}
        """
        device_list = {}

        # Извлекаем уникальные устройства из physical_links и mgmt_networks
        unique_devices = set()

        # Обработка physical_links
        # Структура: [device1, vendor1, type1, interface1, ip1, device2, vendor2, type2, interface2, ip2, network]
        if 'physical_links' in data:
            for link in data['physical_links']:
                if len(link) >= 11:  # Проверяем, что список содержит достаточно элементов
                    device1 = link[0]
                    device2 = link[5]
                    unique_devices.add(device1)
                    unique_devices.add(device2)

        # Обработка mgmt_networks
        # Структура: [device, vendor, type, interface, ip, network]
        if 'mgmt_networks' in data:
            for network in data['mgmt_networks']:
                if len(network) >= 6:  # Проверяем, что список содержит достаточно элементов
                    device = network[0]
                    unique_devices.add(device)

        # Обработка logical_links
        # Структура: [device1, vendor1, type1, interface1, device2, vendor2, type2, interface2, link_type]
        if 'logical_links' in data:
            for link in data['logical_links']:
                if len(link) >= 7:  # Проверяем, что список содержит достаточно элементов
                    device1 = link[0]
                    device2 = link[4]
                    unique_devices.add(device1)
                    unique_devices.add(device2)

        # Для каждого уникального устройства находим соответствующий шаблон
        for device_name in unique_devices:
            # Находим информацию об устройстве в данных
            vendor = None
            device_type = None

            # Ищем vendor и type в physical_links
            if 'physical_links' in data:
                for link in data['physical_links']:
                    if len(link) >= 11:
                        if link[0] == device_name:  # device1
                            vendor = link[1].lower()
                            device_type = link[2].lower()
                            break
                        elif link[5] == device_name:  # device2
                            vendor = link[6].lower()
                            device_type = link[7].lower()
                            break

            # Если не нашли в physical_links, ищем в mgmt_networks
            if not vendor and not device_type and 'mgmt_networks' in data:
                for network in data['mgmt_networks']:
                    if len(network) >= 6:
                        if network[0] == device_name:
                            vendor = network[1].lower()
                            device_type = network[2].lower()
                            break

            # Если всё ещё не нашли vendor и type, ищем в logical_links
            if not vendor and not device_type and 'logical_links' in data:
                for link in data['logical_links']:
                    if len(link) >= 7:
                        if link[0] == device_name:  # device1
                            vendor = link[1].lower()
                            device_type = link[2].lower()
                            break
                        elif link[4] == device_name:  # device2
                            vendor = link[5].lower()
                            device_type = link[6].lower()
                            break

            # Если удалось определить vendor и type, ищем соответствующий шаблон
            if vendor and device_type:
                # Ищем шаблон в словаре patterns
                # patterns имеет структуру: {vendor: [{device_type: template_data}, ...]}
                if vendor.capitalize() in patterns:
                    vendor_patterns = patterns[vendor.capitalize()]
                    
                    # Ищем шаблон для конкретного типа устройства
                    for pattern in vendor_patterns:
                        # pattern - это словарь в формате {device_type: template_data}
                        for key, template_data in pattern.items():
                            if key.lower() == device_type.lower():
                                # Копируем шаблон и добавляем дополнительные поля
                                device_data = template_data.copy()
                                device_data['x'] = 0
                                device_data['y'] = 0
                                device_data['data'] = {}
                                device_list[device_name] = device_data
                                break
                        else:
                            continue  # только если внутренний цикл не был прерван
                        break  # выйти из внешнего цикла, если шаблон найден
            else:
                # Если не удалось определить vendor и type, используем шаблон default из словаря patterns
                # Предполагаем, что шаблон по умолчанию всегда есть в словаре patterns под ключом 'default'
                default_template = None
                
                # Получаем шаблон по умолчанию из ключа 'default'
                if 'default' in patterns:
                    default_patterns = patterns['default']
                    if isinstance(default_patterns, list) and len(default_patterns) > 0:
                        first_pattern = default_patterns[0]
                        if isinstance(first_pattern, dict):
                            for device_type, template_data in first_pattern.items():
                                default_template = template_data
                                break
                
                # Добавляем дополнительные поля к шаблону
                device_data = default_template.copy() if default_template else {}
                device_data['x'] = 0
                device_data['y'] = 0
                device_data['data'] = {}
                device_list[device_name] = device_data

        return device_list

    @staticmethod
    def generate_network_list(data: Dict[str, Any], patterns: Dict[str, Any]) -> Dict[str, Any]:
        """
        Процедура формирования перечня уникальных сетей на основе словарей
        и формирующей словарь где в качестве ключа используется ip_mask
        а в качестве шаблона используется данные шаблона ключ network

        Args:
            data (dict): Словарь с результатами линков, содержащий physical_links, mgmt_networks и logical_links
            patterns (dict): Словарь шаблонов устройств

        Returns:
            dict: Словарь в формате {ip_mask: {данные_из_шаблона_network + дополнительные_поля}}
        """
        network_list = {}

        # Извлекаем уникальные сети из physical_links, mgmt_networks и logical_links
        network_sources = {}  # Словарь для отслеживания источников сетей

        # Обработка physical_links
        # Структура: [device1, vendor1, type1, interface1, ip1, device2, vendor2, type2, interface2, ip2, network]
        if 'physical_links' in data:
            for link in data['physical_links']:
                if len(link) >= 11:  # Проверяем, что список содержит достаточно элементов
                    network = link[10]  # Последний элемент - сеть
                    if network not in network_sources:
                        network_sources[network] = 1  # physical_links
                    elif network_sources[network] != 1:  # Если сеть уже была найдена не в physical_links
                        network_sources[network] = 2  # Обычная сеть (не только logical)

        # Обработка mgmt_networks
        # Структура: [device, vendor, type, interface, ip, network]
        if 'mgmt_networks' in data:
            for network_entry in data['mgmt_networks']:
                if len(network_entry) >= 6:  # Проверяем, что список содержит достаточно элементов
                    network = network_entry[5]  # Последний элемент - сеть
                    if network not in network_sources:
                        network_sources[network] = 2  # mgmt_networks (обычная сеть)
                    elif network_sources[network] != 1:  # Если сеть уже была найдена не в physical_links
                        # Оставляем текущее значение, если это не physical_links
                        pass

        # Обработка logical_links
        # Структура: [device1, vendor1, type1, interface1, device2, vendor2, type2, interface2, link_type]
        # Сети в logical_links могут быть представлены в link_type или других элементах
        # В текущем формате, сеть может быть частью link_type, например "Service Network: 172.23.197.0/24"
        if 'logical_links' in data:
            for link in data['logical_links']:
                if len(link) >= 9:  # Проверяем, что список содержит достаточно элементов
                    link_type = link[8]  # Последний элемент - тип связи
                    # Извлекаем сеть из строки типа связи, если она там содержится
                    if 'Network:' in link_type:
                        # Извлекаем маску сети из строки вида "Service Network: 172.23.197.0/24"
                        parts = link_type.split(':')
                        if len(parts) >= 2:
                            network = parts[1].strip()
                            if network not in network_sources:
                                network_sources[network] = 3  # Только logical_links
                            elif network_sources[network] != 1:  # Если не в physical_links
                                if network_sources[network] == 3:  # Если была только в logical
                                    # Если теперь встречается в других местах, становится обычной сетью
                                    network_sources[network] = 2
                                # Иначе оставляем как есть

        # Теперь формируем словарь сетей с шаблонами
        # Получаем шаблон network из словаря patterns
        network_template = None
        
        # Ищем шаблон network в словаре patterns
        for vendor, vendor_patterns in patterns.items():
            for pattern in vendor_patterns:
                for device_type, template_data in pattern.items():
                    if device_type.lower() == 'network':
                        network_template = template_data
                        break
                if network_template:
                    break
            if network_template:
                break

        # Формируем итоговый словарь
        for network, source_type in network_sources.items():
            # Копируем шаблон и добавляем дополнительные поля
            network_data = network_template.copy()
            network_data['x'] = 0
            network_data['y'] = 0
            network_data['pattern'] = source_type
            network_data['label'] = network
            # Заменяем все символы, кроме цифр, на _
            clean_network_key = ''.join(c if c.isdigit() else '_' for c in network)
            network_list[clean_network_key] = network_data

        return network_list

    @staticmethod
    def generate_links(data: Dict[str, Any], patterns: Dict[str, Any]) -> list:
        """
        Процедура формирования массива словарей, представляющих соединения между устройствами и сетями

        Args:
            data (dict): Словарь с результатами линков, содержащий physical_links, mgmt_networks и logical_links
            patterns (dict): Словарь шаблонов устройств

        Returns:
            list: Массив словарей вида {source, target, style, label, data, src_label}
        """
        links = []

        # Получаем шаблоны для различных типов соединений
        link_styles = {}
        
        # Ищем шаблоны для различных типов соединений в словаре patterns
        if 'common' in patterns:
            for pattern in patterns['common']:
                for link_type, template_data in pattern.items():
                    if link_type.lower() in ['logical_link', 'mgm_link', 'physical_link']:
                        link_styles[link_type.lower()] = template_data

        # Обработка physical_links
        # Структура: [device1, vendor1, type1, interface1, ip1, device2, vendor2, type2, interface2, ip2, network]
        if 'physical_links' in data:
            for link in data['physical_links']:
                if len(link) >= 11:  # Проверяем, что список содержит достаточно элементов
                    device1 = link[0]  # device1
                    interface1 = link[3]  # interface1
                    ip1 = link[4]  # ip1
                    device2 = link[5]  # device2
                    interface2 = link[8]  # interface2
                    ip2 = link[9]  # ip2
                    network = link[10]  # network
                    
                    # Получаем стиль для physical_link
                    style_data = link_styles.get('physical_link', {})
                    style = style_data.get('style', '')
                    
                    # Заменяем все символы, кроме цифр, на _ в target
                    clean_network = ''.join(c if c.isdigit() else '_' for c in network)
                    
                    # Создаем два соединения: от device1 к network и от device2 к network
                    # Соединение от device1 к network
                    link_dict1 = {
                        'source': device1,
                        'target': clean_network,
                        'style': style,
                        'label': ip1,
                        'data': None,
                        'src_label': interface1
                    }
                    links.append(link_dict1)
                    
                    # Соединение от device2 к network
                    link_dict2 = {
                        'source': device2,
                        'target': clean_network,
                        'style': style,
                        'label': ip2,
                        'data': None,
                        'src_label': interface2
                    }
                    links.append(link_dict2)

        # Обработка mgmt_networks
        # Структура: [device, vendor, type, interface, ip, network]
        if 'mgmt_networks' in data:
            for entry in data['mgmt_networks']:
                if len(entry) >= 6:
                    device = entry[0]
                    interface = entry[3]
                    ip = entry[4]
                    network = entry[5]
                    
                    # Получаем стиль для mgm_link
                    style_data = link_styles.get('mgm_link', {})
                    style = style_data.get('style', '')
                    
                    # Заменяем все символы, кроме цифр, на _ в target
                    clean_network = ''.join(c if c.isdigit() else '_' for c in network)
                    
                    # Создаем соединение от устройства к упр. сети
                    link_dict = {
                        'source': device,
                        'target': clean_network,
                        'style': style,
                        'label': ip,
                        'data': None,
                        'src_label': interface
                    }
                    links.append(link_dict)

        # Обработка logical_links
        # Структура: [device1, vendor1, type1, interface1, device2, vendor2, type2, interface2, link_type]
        if 'logical_links' in data:
            for link in data['logical_links']:
                if len(link) >= 9:  # Проверяем, что список содержит достаточно элементов
                    device1 = link[0]  # device1
                    interface1 = link[3]  # interface1
                    device2 = link[4]  # device2
                    interface2 = link[7]  # interface2
                    link_type = link[8]  # link_type (может содержать информацию о сети)
                    
                    # Извлекаем информацию о сети из link_type, если возможно
                    network = link_type
                    ip1 = ""  # В logical_links IP может не быть в явном виде
                    ip2 = ""
                    
                    if ':' in link_type:
                        parts = link_type.split(':', 1)
                        if len(parts) >= 2:
                            network = parts[1].strip()
                    
                    # Получаем стиль для logical_link
                    style_data = link_styles.get('logical_link', {})
                    style = style_data.get('style', '')
                    
                    # Заменяем все символы, кроме цифр, на _ в target
                    clean_network = ''.join(c if c.isdigit() else '_' for c in network)
                    
                    # Создаем два соединения: от device1 к network и от device2 к network
                    # Соединение от device1 к network
                    link_dict1 = {
                        'source': device1,
                        'target': clean_network,
                        'style': style,
                        'label': ip1,
                        'data': None,
                        'src_label': interface1
                    }
                    links.append(link_dict1)
                    
                    # Соединение от device2 к network
                    link_dict2 = {
                        'source': device2,
                        'target': clean_network,
                        'style': style,
                        'label': ip2,
                        'data': None,
                        'src_label': interface2
                    }
                    links.append(link_dict2)

        return links

    def prepare_stencils(self, data : Dict[str, Any], layout_algorithm: str = 'circular'):

        # 1. Формируем словари шаблонов
        patterns = self.merge_yaml_files()

        # 2. Формируем перечень устройств для размещения на диаграмме
        devices = self.generate_device_list(data=data, patterns=patterns)

        # 3. Формируем перечень сетей для размещения на диаграмме
        networks = self.generate_network_list(data=data, patterns=patterns)

        # 4. Формируем перечень линков
        links = self.generate_links(data=data, patterns=patterns)

        # 5. Подготавливаем объекты для алгоритма размещения
        objects = {
            'devices': devices,
            'networks': networks,
            'links': links
        }

        # 6. Вызываем выбранный алгоритм размещения
        if layout_algorithm == 'circular':
            objects = self.layout_algorithm_circular(objects)
        elif layout_algorithm == 'grid':
            objects = self.layout_algorithm_grid(objects)
        elif layout_algorithm == 'force_directed':
            objects = self.layout_algorithm_force_directed(objects)
        elif layout_algorithm == 'clustered':
            objects = self.layout_algorithm_clustered(objects)
        else:
            # По умолчанию используем круговой алгоритм
            objects = self.layout_algorithm_circular(objects)

        return objects

    @staticmethod
    def layout_algorithm_circular(objects: dict, padding: int = 20, circular_padding: int = 250) -> dict:
        """
        Круговой алгоритм размещения объектов с вложенными кругами

        Args:
            objects (dict): Словарь с объектами {'devices': devices, 'networks': networks, 'links': links}
            padding (int): Паддинг вокруг объектов
            circular_padding (int): Отступ между краями окружностей на которых размещаются элементы

        Returns:
            dict: Модифицированный словарь с проставленными координатами
        """
        import math

        devices = objects['devices']
        networks = objects['networks']

        # Определяем, какие элементы будут во внутреннем круге
        inner_group = None
        outer_group = None
        
        if len(devices) <= len(networks):
            # Устройства во внутреннем круге, сети во внешнем
            inner_group = devices
            outer_group = networks
            inner_label = 'devices'
            outer_label = 'networks'
        else:
            # Сети во внутреннем круге, устройства во внешнем
            inner_group = networks
            outer_group = devices
            inner_label = 'networks'
            outer_label = 'devices'

        # Рассчитываем максимальные размеры для корректного определения радиусов
        max_inner_size = 0
        max_outer_size = 0
        
        for obj_data in inner_group.values():
            w = obj_data.get('width', 50)
            h = obj_data.get('height', 50)
            max_inner_size = max(max_inner_size, w, h)
            
        for obj_data in outer_group.values():
            w = obj_data.get('width', 50)
            h = obj_data.get('height', 50)
            max_outer_size = max(max_outer_size, w, h)
        
        max_obj_size = max(max_inner_size, max_outer_size)

        # Рассчитываем радиусы для внутреннего и внешнего кругов
        n_inner = len(inner_group)
        n_outer = len(outer_group)
        
        if n_inner > 0:
            inner_radius = max((n_inner * (max_inner_size + padding)) / (2 * math.pi), max_inner_size + padding)
        else:
            inner_radius = 0
            
        if n_outer > 0:
            # Учитываем высоту элементов и circular_padding для избежания пересечений
            outer_radius = max((n_outer * (max_outer_size + padding)) / (2 * math.pi), inner_radius + max(max_inner_size, max_outer_size) + circular_padding)
        else:
            outer_radius = inner_radius + max_obj_size + circular_padding

        center_x, center_y = 0, 0

        # Размещаем внутренние объекты
        if n_inner > 0:
            # Если внутренняя группа - это сети, то разделяем их на подгруппы по pattern
            if inner_label == 'networks':
                # Группируем сети по значению pattern
                pattern_groups = {}
                for obj_id, obj_data in inner_group.items():
                    pattern_value = obj_data.get('pattern', 0)
                    if pattern_value not in pattern_groups:
                        pattern_groups[pattern_value] = []
                    pattern_groups[pattern_value].append(obj_id)
                
                # Рассчитываем параметры для размещения подгрупп
                n_patterns = len(pattern_groups)
                if n_patterns > 1:
                    # Размещаем каждую подгруппу на отдельном круге с общим центром
                    # Рассчитываем радиусы для каждой подгруппы с учетом высоты элементов и circular_padding
                    # Нужно учитывать максимальную высоту элементов в каждой группе
                    pattern_max_heights = {}
                    for pattern_val, pattern_networks in pattern_groups.items():
                        max_h = 0
                        for obj_id in pattern_networks:
                            h = inner_group[obj_id].get('height', 50)
                            max_h = max(max_h, h)
                        pattern_max_heights[pattern_val] = max_h
                    
                    # Рассчитываем радиусы с учетом высоты элементов и circular_padding
                    # Начинаем с минимального радиуса и увеличиваем его для каждой группы
                    current_radius = circular_padding  # Минимальный радиус
                    for idx, (pattern_val, pattern_networks) in enumerate(pattern_groups.items()):
                        n_subgroup = len(pattern_networks)
                        if n_subgroup > 0:
                            # Рассчитываем радиус для этой подгруппы с учетом высоты элементов
                            max_height = pattern_max_heights[pattern_val]
                            
                            subgroup_radius = current_radius
                            subgroup_angle_step = 2 * math.pi / n_subgroup
                            
                            for j, obj_id in enumerate(pattern_networks):
                                angle = j * subgroup_angle_step
                                x = center_x + subgroup_radius * math.cos(angle) - inner_group[obj_id].get('width', 50) / 2
                                y = center_y + subgroup_radius * math.sin(angle) - inner_group[obj_id].get('height', 50) / 2

                                # Округляем координаты до ближайшего целого
                                x = round(x)
                                y = round(y)

                                objects['networks'][obj_id]['x'] = x
                                objects['networks'][obj_id]['y'] = y
                            
                            # Увеличиваем радиус для следующей группы
                            current_radius += max_height + circular_padding
                        else:
                            # Если в подгруппе нет элементов, размещаем в центре
                            obj_id = pattern_networks[0]
                            x = center_x - inner_group[obj_id].get('width', 50) / 2
                            y = center_y - inner_group[obj_id].get('height', 50) / 2

                            # Округляем координаты до ближайшего целого
                            x = round(x)
                            y = round(y)

                            objects['networks'][obj_id]['x'] = x
                            objects['networks'][obj_id]['y'] = y
                else:
                    # Если только одна группа по pattern, размещаем как обычно
                    inner_angle_step = 2 * math.pi / n_inner if n_inner > 0 else 0
                    for i, obj_id in enumerate(inner_group.keys()):
                        angle = i * inner_angle_step
                        x = center_x + inner_radius * math.cos(angle) - inner_group[obj_id].get('width', 50) / 2
                        y = center_y + inner_radius * math.sin(angle) - inner_group[obj_id].get('height', 50) / 2

                        # Округляем координаты до ближайшего целого
                        x = round(x)
                        y = round(y)

                        # Обновляем координаты в соответствующем словаре
                        objects['networks'][obj_id]['x'] = x
                        objects['networks'][obj_id]['y'] = y
            else:
                # Если внутренняя группа - устройства, размещаем как обычно
                inner_angle_step = 2 * math.pi / n_inner if n_inner > 0 else 0
                for i, obj_id in enumerate(inner_group.keys()):
                    angle = i * inner_angle_step
                    x = center_x + inner_radius * math.cos(angle) - inner_group[obj_id].get('width', 50) / 2
                    y = center_y + inner_radius * math.sin(angle) - inner_group[obj_id].get('height', 50) / 2

                    # Округляем координаты до ближайшего целого
                    x = round(x)
                    y = round(y)

                    # Обновляем координаты в соответствующем словаре
                    objects['devices'][obj_id]['x'] = x
                    objects['devices'][obj_id]['y'] = y

        # Размещаем внешние объекты
        if n_outer > 0:
            # Если внешняя группа - это сети, то разделяем их на подгруппы по pattern
            if outer_label == 'networks':
                # Группируем сети по значению pattern
                pattern_groups = {}
                for obj_id, obj_data in outer_group.items():
                    pattern_value = obj_data.get('pattern', 0)
                    if pattern_value not in pattern_groups:
                        pattern_groups[pattern_value] = []
                    pattern_groups[pattern_value].append(obj_id)
                
                # Рассчитываем параметры для размещения подгрупп
                n_patterns = len(pattern_groups)
                if n_patterns > 1:
                    # Размещаем каждую подгруппу на отдельном круге с общим центром
                    # Рассчитываем радиусы для каждой подгруппы с учетом высоты элементов и circular_padding
                    # Нужно учитывать максимальную высоту элементов в каждой группе
                    pattern_max_heights = {}
                    for pattern_val, pattern_networks in pattern_groups.items():
                        max_h = 0
                        for obj_id in pattern_networks:
                            h = outer_group[obj_id].get('height', 50)
                            max_h = max(max_h, h)
                        pattern_max_heights[pattern_val] = max_h
                    
                    # Рассчитываем радиусы с учетом высоты элементов и circular_padding
                    # Начинаем с минимального радиуса и увеличиваем его для каждой группы
                    current_radius = outer_radius - (sum(pattern_max_heights.values()) + (n_patterns - 1) * circular_padding)
                    if current_radius < 0:
                        current_radius = circular_padding  # Минимальный радиус
                    
                    for idx, (pattern_val, pattern_networks) in enumerate(pattern_groups.items()):
                        n_subgroup = len(pattern_networks)
                        if n_subgroup > 0:
                            # Рассчитываем радиус для этой подгруппы с учетом высоты элементов
                            max_height = pattern_max_heights[pattern_val]
                            
                            subgroup_radius = current_radius
                            subgroup_angle_step = 2 * math.pi / n_subgroup
                            
                            for j, obj_id in enumerate(pattern_networks):
                                angle = j * subgroup_angle_step
                                x = center_x + subgroup_radius * math.cos(angle) - outer_group[obj_id].get('width', 50) / 2
                                y = center_y + subgroup_radius * math.sin(angle) - outer_group[obj_id].get('height', 50) / 2

                                # Округляем координаты до ближайшего целого
                                x = round(x)
                                y = round(y)

                                objects['networks'][obj_id]['x'] = x
                                objects['networks'][obj_id]['y'] = y
                            
                            # Увеличиваем радиус для следующей группы
                            current_radius += max_height + circular_padding
                        else:
                            # Если в подгруппе нет элементов, размещаем в центре
                            obj_id = pattern_networks[0]
                            x = center_x - outer_group[obj_id].get('width', 50) / 2
                            y = center_y - outer_group[obj_id].get('height', 50) / 2

                            # Округляем координаты до ближайшего целого
                            x = round(x)
                            y = round(y)

                            objects['networks'][obj_id]['x'] = x
                            objects['networks'][obj_id]['y'] = y
                else:
                    # Если только одна группа по pattern, размещаем как обычно
                    outer_angle_step = 2 * math.pi / n_outer if n_outer > 0 else 0
                    for i, obj_id in enumerate(outer_group.keys()):
                        angle = i * outer_angle_step
                        x = center_x + outer_radius * math.cos(angle) - outer_group[obj_id].get('width', 50) / 2
                        y = center_y + outer_radius * math.sin(angle) - outer_group[obj_id].get('height', 50) / 2

                        # Округляем координаты до ближайшего целого
                        x = round(x)
                        y = round(y)

                        # Обновляем координаты в соответствующем словаре
                        objects['networks'][obj_id]['x'] = x
                        objects['networks'][obj_id]['y'] = y
            else:
                # Если внешняя группа - устройства, размещаем как обычно
                outer_angle_step = 2 * math.pi / n_outer if n_outer > 0 else 0
                for i, obj_id in enumerate(outer_group.keys()):
                    angle = i * outer_angle_step
                    x = center_x + outer_radius * math.cos(angle) - outer_group[obj_id].get('width', 50) / 2
                    y = center_y + outer_radius * math.sin(angle) - outer_group[obj_id].get('height', 50) / 2

                    # Округляем координаты до ближайшего целого
                    x = round(x)
                    y = round(y)

                    # Обновляем координаты в соответствующем словаре
                    objects['devices'][obj_id]['x'] = x
                    objects['devices'][obj_id]['y'] = y

        return objects

    @staticmethod
    def layout_algorithm_grid(objects: dict, padding: int = 50, group_padding: int = 30) -> dict:
        """
        Сеточный алгоритм размещения объектов с группировкой сетей по pattern

        Args:
            objects (dict): Словарь с объектами {'devices': devices, 'networks': networks, 'links': links}
            padding (int): Паддинг вокруг объектов
            group_padding (int): Отступ между группами объектов

        Returns:
            dict: Модифицированный словарь с проставленными координатами
        """
        import math

        devices = objects['devices']
        networks = objects['networks']
        links = objects['links']

        # 1. Разбиение на группы и определение сеток
        # Группируем сети по значению pattern
        network_groups = {}
        for network_id, network_data in networks.items():
            pattern_value = network_data.get('pattern', 0)
            if pattern_value not in network_groups:
                network_groups[pattern_value] = {}
            network_groups[pattern_value][network_id] = network_data

        # Определяем все группы (устройства и группы сетей)
        all_groups = {'devices': devices}
        for pattern, net_group in network_groups.items():
            all_groups[f'network_{pattern}'] = net_group

        # 2. Предварительный расчет координат устройств и сетей внутри каждой из групп
        # и определение границ сетки группы
        group_bounds = {}  # Словарь для хранения границ каждой группы
        group_relative_positions = {}  # Словарь для хранения относительных координат объектов в группе

        for group_name, group_objects in all_groups.items():
            if not group_objects:
                continue

            # Рассчитываем сетку для текущей группы
            n = len(group_objects)
            if n == 0:
                continue

            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols) if cols > 0 else 0

            current_x, current_y = 0, 0
            max_row_height = 0
            i = 0

            group_relative_positions[group_name] = {}

            for obj_id in group_objects.keys():
                obj_data = group_objects[obj_id]
                width = obj_data.get('width', 50)
                height = obj_data.get('height', 50)

                # Сохраняем относительные координаты
                group_relative_positions[group_name][obj_id] = (current_x, current_y)

                max_row_height = max(max_row_height, height)

                # Переходим к следующей позиции
                # Паддинг справа и слева равен ширине объекта + padding
                current_x += width + padding
                if (i + 1) % cols == 0:  # Новая строка
                    current_x = 0
                    # Паддинг по высоте равен высоте объекта + padding
                    current_y += max_row_height + padding
                    max_row_height = 0

                i += 1

            # Определяем границы группы с учетом padding по периметру
            if n > 0:
                # Находим максимальные координаты
                max_x = max(pos[0] for pos in group_relative_positions[group_name].values())
                max_y = max(pos[1] for pos in group_relative_positions[group_name].values())
                
                # Находим ширину и высоту последнего элемента
                last_obj = list(group_objects.values())[-1]
                last_width = last_obj.get('width', 50)
                last_height = last_obj.get('height', 50)
                
                # Определяем общую ширину и высоту группы
                group_width = max_x + last_width
                group_height = max_y + last_height
                
                # Добавляем padding по периметру
                padded_width = group_width + 2 * padding
                padded_height = group_height + 2 * padding
                
                group_bounds[group_name] = {
                    'width': padded_width,
                    'height': padded_height,
                    'original_width': group_width,
                    'original_height': group_height
                }

        # 3. Формирование общей сетки для размещения каждого из блоков (сеток групп)
        # где каждый из блоков рассматривается как макрообъект
        n_groups = len(group_bounds)
        if n_groups == 0:
            return objects

        # Рассчитываем сетку для размещения групп
        group_cols = math.ceil(math.sqrt(n_groups))
        group_rows = math.ceil(n_groups / group_cols) if group_cols > 0 else 0

        # Определяем размеры общей сетки
        macro_current_x, macro_current_y = 0, 0
        macro_max_row_height = 0
        group_macro_positions = {}

        group_names_list = list(group_bounds.keys())
        for i, group_name in enumerate(group_names_list):
            group_width = group_bounds[group_name]['width']
            group_height = group_bounds[group_name]['height']

            group_macro_positions[group_name] = (macro_current_x, macro_current_y)

            macro_max_row_height = max(macro_max_row_height, group_height)

            # Переходим к следующей позиции
            macro_current_x += group_width + group_padding
            if (i + 1) % group_cols == 0:  # Новая строка
                macro_current_x = 0
                macro_current_y += macro_max_row_height + group_padding
                macro_max_row_height = 0

        # 4. Пересчет координат устройств и сетей внутри каждого из блоков
        # с учетом координат блока внутри общей сетки
        for group_name, group_objects in all_groups.items():
            if group_name not in group_macro_positions:
                continue

            # Получаем позицию группы в общей сетке
            group_pos_x, group_pos_y = group_macro_positions[group_name]

            # Обновляем координаты для каждого объекта в группе
            for obj_id in group_objects.keys():
                if group_name in group_relative_positions and obj_id in group_relative_positions[group_name]:
                    rel_x, rel_y = group_relative_positions[group_name][obj_id]
                    
                    # Абсолютная позиция = позиция группы + относительная позиция объекта в группе
                    abs_x = group_pos_x + rel_x + padding  # добавляем padding для компенсации периметра
                    abs_y = group_pos_y + rel_y + padding
                    
                    # Обновляем координаты в основном словаре
                    if obj_id in objects['devices']:
                        objects['devices'][obj_id]['x'] = abs_x
                        objects['devices'][obj_id]['y'] = abs_y
                    elif obj_id in objects['networks']:
                        objects['networks'][obj_id]['x'] = abs_x
                        objects['networks'][obj_id]['y'] = abs_y

        # Округляем все координаты до целых чисел
        for device_id, device_data in objects['devices'].items():
            device_data['x'] = round(device_data['x'])
            device_data['y'] = round(device_data['y'])

        for network_id, network_data in objects['networks'].items():
            network_data['x'] = round(network_data['x'])
            network_data['y'] = round(network_data['y'])

        return objects

    @staticmethod
    def layout_algorithm_force_directed(objects: dict, padding: int = 5) -> dict:
        """
        Улучшенный алгоритм силовой направленности для размещения объектов

        Args:
            objects (dict): Словарь с объектами {'devices': devices, 'networks': networks, 'links': links}
            padding (int): padding вокруг объектов

        Returns:
            dict: Модифицированный словарь с проставленными координатами
        """
        import random
        import math

        all_objects = {}
        all_objects.update(objects['devices'])
        all_objects.update(objects['networks'])

        n = len(all_objects)
        if n <= 1:
            # Если один или нет объектов, просто размещаем в начале координат
            for obj_id in all_objects.keys():
                if obj_id in objects['devices']:
                    objects['devices'][obj_id]['x'] = 0
                    objects['devices'][obj_id]['y'] = 0
                elif obj_id in objects['networks']:
                    objects['networks'][obj_id]['x'] = 0
                    objects['networks'][obj_id]['y'] = 0
            return objects

        # Инициализация позиций по кругу для более равномерного распределения
        positions = {}
        angle_step = 2 * math.pi / n if n > 0 else 0
        radius = max(100, n * 30)  # Увеличенный радиус для большего начального расстояния

        for i, obj_id in enumerate(all_objects.keys()):
            angle = i * angle_step
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            positions[obj_id] = [x, y]

        # Создаем граф на основе связей
        graph = {}
        for link in objects['links']:
            source = link['source']
            target = link['target']

            if source not in graph:
                graph[source] = []
            if target not in graph:
                graph[target] = []

            if target not in graph[source]:
                graph[source].append(target)
            if source not in graph[target]:
                graph[target].append(source)

        # Параметры алгоритма
        k_repulsion_device_device = 50  # Коэффициент отталкивания между устройствами
        k_repulsion_network_network = 40  # Коэффициент отталкивания между сетями
        k_repulsion_device_network = 60  # Коэффициент отталкивания между устройствами и сетями
        k_attraction = 0.8  # Коэффициент притяжения
        iterations = 100  # Увеличенное количество итераций для лучшей сходимости
        initial_temperature = 150  # Начальная температура для ограничения смещений

        for iteration in range(iterations):
            displacement = {node: [0, 0] for node in positions}

            # Сила отталкивания между узлами с учетом типов объектов и их размеров
            for v in positions:
                for u in positions:
                    if v != u:
                        dx = positions[v][0] - positions[u][0]
                        dy = positions[v][1] - positions[u][1]
                        
                        # Учитываем размеры объектов при расчете расстояния
                        v_width = all_objects[v].get('width', 50)
                        v_height = all_objects[v].get('height', 50)
                        u_width = all_objects[u].get('width', 50)
                        u_height = all_objects[u].get('height', 50)
                        
                        # Минимальное расстояние между центрами объектов с учетом их размеров и паддинга
                        min_distance = (math.sqrt(v_width**2 + v_height**2) + math.sqrt(u_width**2 + u_height**2))/2 + padding
                        
                        distance = max(math.sqrt(dx*dx + dy*dy), 0.1)

                        # Определяем типы объектов для выбора коэффициента отталкивания
                        v_is_device = v in objects['devices']
                        u_is_device = u in objects['devices']
                        
                        if v_is_device and u_is_device:
                            k_repulsion = k_repulsion_device_device
                        elif not v_is_device and not u_is_device:
                            k_repulsion = k_repulsion_network_network
                        else:
                            k_repulsion = k_repulsion_device_network
                        
                        # Отталкивающая сила (с учетом минимального расстояния)
                        if distance < min_distance:
                            # Если объекты слишком близко, увеличиваем силу отталкивания
                            repulsion_force = k_repulsion * k_repulsion / distance * (min_distance / distance)**2
                        else:
                            repulsion_force = k_repulsion * k_repulsion / distance
                        
                        displacement[v][0] += (dx / distance) * repulsion_force
                        displacement[v][1] += (dy / distance) * repulsion_force

            # Сила притяжения для связанных узлов
            for node in graph:
                if node in positions:  # Проверяем, что узел существует в positions
                    for neighbor in graph[node]:
                        if neighbor in positions:  # Проверяем, что сосед существует в positions
                            dx = positions[neighbor][0] - positions[node][0]
                            dy = positions[neighbor][1] - positions[node][1]
                            distance = max(math.sqrt(dx*dx + dy*dy), 0.1)

                            # Притягивающая сила (чем дальше, тем сильнее притяжение)
                            attraction_force = (distance * distance) * k_attraction / (k_repulsion_device_network if (node in objects['devices']) != (neighbor in objects['devices']) else k_repulsion_device_device)
                            
                            # Ограничиваем силу притяжения, чтобы не было чрезмерного сближения
                            max_attraction = 50
                            attraction_force = min(attraction_force, max_attraction)
                            
                            displacement[node][0] += (dx / distance) * attraction_force
                            displacement[node][1] += (dy / distance) * attraction_force

            # Обновляем позиции с учетом температуры
            temperature = initial_temperature * (1 - iteration / iterations)  # Постепенно снижаем температуру

            for node in positions:
                move_x = max(min(displacement[node][0], temperature), -temperature)
                move_y = max(min(displacement[node][1], temperature), -temperature)

                positions[node][0] += move_x
                positions[node][1] += move_y

        # Проверяем и устраняем наложения после основного цикла
        positions = NetworkVisualizer._resolve_overlaps(positions, all_objects, padding)

        # Нормализуем позиции и применяем к объектам
        if positions:
            min_x = min(pos[0] for pos in positions.values())
            min_y = min(pos[1] for pos in positions.values())

            for obj_id, pos in positions.items():
                x = pos[0] - min_x
                y = pos[1] - min_y

                # Учитываем размеры объекта
                width = all_objects[obj_id].get('width', 50)
                height = all_objects[obj_id].get('height', 50)

                if obj_id in objects['devices']:
                    objects['devices'][obj_id]['x'] = x - width/2
                    objects['devices'][obj_id]['y'] = y - height/2
                elif obj_id in objects['networks']:
                    objects['networks'][obj_id]['x'] = x - width/2
                    objects['networks'][obj_id]['y'] = y - height/2

        return objects

    @staticmethod
    def _resolve_overlaps(positions: dict, all_objects: dict, padding: int = 50) -> dict:
        """
        Метод для устранения наложений объектов после основного алгоритма
        
        Args:
            positions (dict): Текущие позиции объектов
            all_objects (dict): Все объекты с информацией о размерах
            padding (int): Паддинг между объектами
            
        Returns:
            dict: Обновленные позиции без наложений
        """
        import math
        
        # Создаем копию позиций для модификации
        new_positions = positions.copy()
        
        # Повторяем процесс устранения наложений несколько раз
        for _ in range(5):  # 5 итераций для устранения наложений
            overlaps_found = False
            
            for obj1, pos1 in new_positions.items():
                for obj2, pos2 in new_positions.items():
                    if obj1 != obj2:
                        # Получаем размеры объектов
                        w1 = all_objects[obj1].get('width', 50)
                        h1 = all_objects[obj1].get('height', 50)
                        w2 = all_objects[obj2].get('width', 50)
                        h2 = all_objects[obj2].get('height', 50)
                        
                        # Проверяем наложение по осям X и Y
                        x_overlap = abs(pos1[0] - pos2[0]) < (w1/2 + w2/2 + padding)
                        y_overlap = abs(pos1[1] - pos2[1]) < (h1/2 + h2/2 + padding)
                        
                        if x_overlap and y_overlap:
                            # Обнаружено наложение, сдвигаем объекты
                            dx = pos2[0] - pos1[0]
                            dy = pos2[1] - pos1[1]
                            distance = max(math.sqrt(dx*dx + dy*dy), 0.1)
                            
                            # Рассчитываем минимальное расстояние для предотвращения наложения
                            min_dist = (math.sqrt(w1**2 + h1**2) + math.sqrt(w2**2 + h2**2))/2 + padding
                            
                            # Направление раздвижения
                            move_x = (dx / distance) * min_dist/2
                            move_y = (dy / distance) * min_dist/2
                            
                            # Сдвигаем оба объекта в противоположные стороны
                            new_positions[obj1][0] -= move_x
                            new_positions[obj1][1] -= move_y
                            new_positions[obj2][0] += move_x
                            new_positions[obj2][1] += move_y
                            
                            overlaps_found = True
            
            # Если наложений не найдено, можно прекратить итерации
            if not overlaps_found:
                break
        
        return new_positions

    @staticmethod
    def layout_algorithm_clustered(objects: dict, padding: int = 50) -> dict:
        """
        Кластерный алгоритм размещения объектов - группировка связанных объектов
        
        Args:
            objects (dict): Словарь с объектами {'devices': devices, 'networks': networks, 'links': links}
            padding (int): Паддинг вокруг объектов
            
        Returns:
            dict: Модифицированный словарь с проставленными координатами
        """
        import math
        
        all_objects = {}
        all_objects.update(objects['devices'])
        all_objects.update(objects['networks'])
        
        if len(all_objects) == 0:
            return objects
        
        # Создаем группы связанных объектов
        visited = set()
        clusters = []
        
        # Создаем граф на основе связей
        graph = {}
        for link in objects['links']:
            source = link['source']
            target = link['target']
            
            if source not in graph:
                graph[source] = []
            if target not in graph:
                graph[target] = []
                
            if target not in graph[source]:
                graph[source].append(target)
            if source not in graph[target]:
                graph[target].append(source)
        
        # Находим компоненты связности (кластеры)
        for obj_id in all_objects.keys():
            if obj_id not in visited:
                cluster = []
                queue = [obj_id]
                visited.add(obj_id)
                
                while queue:
                    current = queue.pop(0)
                    cluster.append(current)
                    
                    if current in graph:
                        for neighbor in graph[current]:
                            if neighbor not in visited and neighbor in all_objects:
                                visited.add(neighbor)
                                queue.append(neighbor)
                
                clusters.append(cluster)
        
        # Размещаем каждый кластер отдельно
        current_x, current_y = 0, 0
        max_cluster_height = 0
        
        for cluster in clusters:
            # Для каждого кластера используем сеточный алгоритм
            cluster_size = len(cluster)
            if cluster_size == 1:
                obj_id = cluster[0]
                width = all_objects[obj_id].get('width', 50)
                height = all_objects[obj_id].get('height', 50)
                
                if obj_id in objects['devices']:
                    objects['devices'][obj_id]['x'] = current_x
                    objects['devices'][obj_id]['y'] = current_y
                elif obj_id in objects['networks']:
                    objects['networks'][obj_id]['x'] = current_x
                    objects['networks'][obj_id]['y'] = current_y
                
                current_x += max(width, height) + padding
                max_cluster_height = max(max_cluster_height, height)
            else:
                # Размещаем объекты кластера в сетке
                cols = math.ceil(math.sqrt(cluster_size))
                rows = math.ceil(cluster_size / cols) if cols > 0 else 0
                
                cluster_start_x = current_x
                cluster_start_y = current_y
                
                i = 0
                cluster_max_height = 0
                
                for obj_id in cluster:
                    row = i // cols
                    col = i % cols
                    
                    obj_width = all_objects[obj_id].get('width', 50)
                    obj_height = all_objects[obj_id].get('height', 50)
                    
                    x = cluster_start_x + col * (obj_width + padding)
                    y = cluster_start_y + row * (obj_height + padding)
                    
                    if obj_id in objects['devices']:
                        objects['devices'][obj_id]['x'] = x
                        objects['devices'][obj_id]['y'] = y
                    elif obj_id in objects['networks']:
                        objects['networks'][obj_id]['x'] = x
                        objects['networks'][obj_id]['y'] = y
                    
                    cluster_max_height = max(cluster_max_height, obj_height)
                    i += 1
                
                # Обновляем глобальные координаты
                current_x += cols * (max([all_objects[obj_id].get('width', 50) for obj_id in cluster]) + padding)
                max_cluster_height = max(max_cluster_height, rows * cluster_max_height + padding)
        
        return objects

    def create_drawio_diagram(self, objects: dict ):
        """
        Создает диаграмму draw.io из словаря объектов
        
        Args:
            objects (dict): Словарь с объектами {'devices': devices, 'networks': networks, 'links': links}
        """
        diagram = drawio_diagram()
        diagram.from_file(filename=self.drawio_template)

        # Добавляем на диаграмму устройства и сети
        object_types = {
            'devices': ('устройства', 'устройство'),
            'networks': ('сети', 'сеть')
        }
        print("=" * 110)

        for obj_key, (plural_name, singular_name) in object_types.items():
            objects_dict = objects.get(obj_key, {})
            total = len(objects_dict)
            added = 0
            errors = 0

            for obj_id, obj_data in objects_dict.items():
                try:
                    # Добавляем объект на диаграмму
                    diagram.add_node(
                        id=obj_id,
                        x_pos=obj_data.get('x', 0),
                        y_pos=obj_data.get('y', 0),
                        width=obj_data.get('width', 100),
                        height=obj_data.get('height', 50),
                        style=obj_data.get('style', ''),
                        label=obj_data.get('label', obj_id)
                    )
                    added += 1

                except Exception as e:
                    errors += 1
                    print(f"Ошибка при добавлении {singular_name} {obj_id}: {e}")

            # Вывод статистики для текущего типа объектов
            print(f"Добавлено {plural_name}: {added}/{total}, ошибок: {errors}")


        # Сохраняем диаграмму
        diagram.dump_file(filename="network_diagram.drawio", folder="./")



