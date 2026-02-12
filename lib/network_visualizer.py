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
    def layout_algorithm_circular(objects: dict, padding: int = 50) -> dict:
        """
        Круговой алгоритм размещения объектов
        
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
        
        n = len(all_objects)
        if n == 0:
            return objects
            
        # Рассчитываем радиус окружности
        max_width_height = 0
        for obj_data in all_objects.values():
            w = obj_data.get('width', 50)
            h = obj_data.get('height', 50)
            max_width_height = max(max_width_height, w, h)
        
        radius = max((n * (max_width_height + padding)) / (2 * math.pi), max_width_height + padding)
        
        center_x, center_y = 0, 0
        angle_step = 2 * math.pi / n if n > 0 else 0
        
        i = 0
        for obj_id in all_objects.keys():
            angle = i * angle_step
            x = center_x + radius * math.cos(angle) - all_objects[obj_id].get('width', 50) / 2
            y = center_y + radius * math.sin(angle) - all_objects[obj_id].get('height', 50) / 2
            
            # Обновляем координаты в соответствующем словаре
            if obj_id in objects['devices']:
                objects['devices'][obj_id]['x'] = x
                objects['devices'][obj_id]['y'] = y
            elif obj_id in objects['networks']:
                objects['networks'][obj_id]['x'] = x
                objects['networks'][obj_id]['y'] = y
            i += 1
            
        return objects

    @staticmethod
    def layout_algorithm_grid(objects: dict, padding: int = 50) -> dict:
        """
        Сеточный алгоритм размещения объектов
        
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
        
        n = len(all_objects)
        if n == 0:
            return objects
            
        # Определяем размер сетки
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols) if cols > 0 else 0
        
        current_x, current_y = 0, 0
        max_row_height = 0
        
        i = 0
        for obj_id in all_objects.keys():
            obj_data = all_objects[obj_id]
            width = obj_data.get('width', 50)
            height = obj_data.get('height', 50)
            
            # Обновляем координаты
            if obj_id in objects['devices']:
                objects['devices'][obj_id]['x'] = current_x
                objects['devices'][obj_id]['y'] = current_y
            elif obj_id in objects['networks']:
                objects['networks'][obj_id]['x'] = current_x
                objects['networks'][obj_id]['y'] = current_y
            
            max_row_height = max(max_row_height, height)
            
            # Переходим к следующей позиции
            current_x += width + padding
            if (i + 1) % cols == 0:  # Новая строка
                current_x = 0
                current_y += max_row_height + padding
                max_row_height = 0
            
            i += 1
            
        return objects

    @staticmethod
    def layout_algorithm_force_directed(objects: dict, padding: int = 50) -> dict:
        """
        Алгоритм силовой направленности для размещения объектов
        
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
        radius = max(100, n * 20)  # Радиус зависит от количества объектов
        
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
        k_repulsion = 30  # Коэффициент отталкивания
        k_attraction = 0.5  # Коэффициент притяжения
        iterations = 50  # Количество итераций
        initial_temperature = 100  # Начальная температура для ограничения смещений
        
        for iteration in range(iterations):
            displacement = {node: [0, 0] for node in positions}
            
            # Сила отталкивания между узлами
            for v in positions:
                for u in positions:
                    if v != u:
                        dx = positions[v][0] - positions[u][0]
                        dy = positions[v][1] - positions[u][1]
                        distance = max(math.sqrt(dx*dx + dy*dy), 0.1)
                        
                        # Отталкивающая сила (чем ближе, тем сильнее отталкивание)
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
                            attraction_force = (distance * distance) * k_attraction / k_repulsion
                            displacement[node][0] += (dx / distance) * attraction_force
                            displacement[node][1] += (dy / distance) * attraction_force
            
            # Обновляем позиции с учетом температуры
            temperature = initial_temperature * (1 - iteration / iterations)  # Постепенно снижаем температуру
            
            for node in positions:
                move_x = max(min(displacement[node][0], temperature), -temperature)
                move_y = max(min(displacement[node][1], temperature), -temperature)
                
                positions[node][0] += move_x
                positions[node][1] += move_y
        
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
                        style=obj_data.get('style', '')
                    )
                    added += 1

                    # Сохраняем отладочную печать только для устройств (как в оригинале)
                    if obj_key == 'devices':
                        print(obj_id)

                except Exception as e:
                    errors += 1
                    print(f"Ошибка при добавлении {singular_name} {obj_id}: {e}")

            # Вывод статистики для текущего типа объектов
            print(f"Добавлено {plural_name}: {added}/{total}, ошибок: {errors}")


        # Сохраняем диаграмму
        diagram.dump_file(filename="network_diagram.drawio", folder="./")



