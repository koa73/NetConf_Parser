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

    def merge_yaml_files(self) -> Dict[str, Any]:
        """
        Reads index.yaml file, reads devices.yaml from the same directory,
        and replaces string values in index with corresponding dictionaries from devices.yaml.

        Args:
            index_path: Path to the index.yaml file

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

        # Если шаблон network не найден, используем fallback
        if not network_template:
            network_template = {
                'height': 20,
                'width': 200,
                'style': 'style="verticalAlign=middle;align=center;vsdxID=35397;rotation=270;fillColor=#c0cfe2;gradientColor=none;shape=stencil(nZFLDsIwDERP4y0KyQKxLuUCnCAihliEpEpL+ZyetANS6YJFs7JnXmxpTKZqvW2YtGq7nC58F9d5MjvSWqLnLF2pyNRkqlPKfM7pFh36xhZSq1Fhhz/rgdbK5uNBXgxts9r+PjAYck39sPwBVMF6foYp9HugQeIE/ZqL4D/oQnC2vhRjPAhOQkC6U38eZ5FwClO/AQ==);strokeColor=#000000;labelBackgroundColor=none;rounded=1;html=1;whiteSpace=wrap;"'
            }

        # Формируем итоговый словарь
        for network, source_type in network_sources.items():
            # Копируем шаблон и добавляем дополнительные поля
            network_data = network_template.copy()
            network_data['x'] = 0
            network_data['y'] = 0
            network_data['pattern'] = source_type
            network_list[network] = network_data

        return network_list

    def prepare_stencils(self, data : Dict[str, Any]):

        # 1. Формируем словари шаблонов
        patterns = self.merge_yaml_files()

        # 2. Формируем перечень устройств для размещения на диаграмме
        devices = self.generate_device_list(data=data, patterns=patterns)

        # 3. Формируем перечень сетей для размещения на диаграмме
        networks = self.generate_network_list(data=data, patterns=patterns)

        print(f'{networks}')


