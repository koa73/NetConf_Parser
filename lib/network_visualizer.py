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

    def prepare_stencils(self, links: Dict[str, Any]):
        print(self.merge_yaml_files())


