import os
from lib.device_analyzer import *
from lib.network_visualizer import NetworkVisualizer
from lib.seaf_converter import DrawioConverter

CONFIG_DIR = "./data_10"
PATTERNS_DIR = "./patterns"
PATTERNS_DIR_DEV = os.path.join(PATTERNS_DIR, "devices")
DRAWIO_TEMPLATES = os.path.join(PATTERNS_DIR, "drawio")
STENCIL_TEMPLATES = os.path.join(DRAWIO_TEMPLATES, "templates")
REPORT = "network_details.txt"
DIAGRAM = "network_diagram.drawio"
SEAF_YAML = "seaf.yaml"


def main():
    # Инициализация загрузчика шаблонов
    pattern_loader = VendorPatternLoader(PATTERNS_DIR_DEV)
    vendor_patterns = pattern_loader.load_patterns()

    # Анализ устройств
    if not os.path.exists(CONFIG_DIR):
        print(f"⚠️  Каталог конфигураций не найден: {CONFIG_DIR}")
        sys.exit(1)

    config_files = [f for f in os.listdir(CONFIG_DIR) if os.path.isfile(os.path.join(CONFIG_DIR, f))]

    if not config_files:
        sys.stderr.write(f"📂 В каталоге '{CONFIG_DIR}' нет файлов для анализа.\n")
        sys.exit(1)

    devices = []
    for config_file in config_files:
        filepath = os.path.join(CONFIG_DIR, config_file)
        device = NetworkDevice(filepath, vendor_patterns)
        if device.analyze():
            devices.append(device.to_dict())

    # Анализ топологии
    t = NetworkTopologyAnalyzer()
    links_result = t.analyze_topology(devices)

    # Генерация отчётов
    ReportGenerator.print_short_report(devices)
    ReportGenerator.print_topology_analysis(links_result)
    ReportGenerator.write_detailed_report(devices, REPORT, links_result, CONFIG_DIR)
    
    # Генерация текстовой ASCII-диаграммы топологии
    ReportGenerator.draw_topology_ascii(devices, links_result, REPORT)

    if links_result:
        print(f"⚠️  Создаю диаграмму\n")

        # Генерация сетевой диаграммы
        viz = NetworkVisualizer(
            pattern_dir=DRAWIO_TEMPLATES, drawio_template=DRAWIO_TEMPLATES + "/base.drawio",
            drawio_stencil_templates=STENCIL_TEMPLATES
        )

        # Выводим меню выбора алгоритма размещения
        print("Выберите алгоритм размещения объектов на диаграмме:")
        print("1. Круговой алгоритм")
        print("2. Сеточный алгоритм")
        print("3. Силовой алгоритм")
        print("4. Кластерный алгоритм")
        print("5. Spine-Leaf-Border Leaf (оптимально для CLOS архитектуры)")
        print("\nНажмите Enter для выбора алгоритма по умолчанию (Spine-Leaf-Border Leaf)\n")

        choice = input("Введите номер алгоритма (1-5) или нажмите Enter: ").strip()

        # Определяем название алгоритма на основе выбора пользователя
        algorithm_map = {
            '1': 'circular',
            '2': 'grid',
            '3': 'force_directed',
            '4': 'clustered',
            '5': 'spine_leaf'
        }

        layout_algorithm = algorithm_map.get(choice, 'spine_leaf')  # По умолчанию Spine-Leaf

        objects = viz.prepare_stencils(links_result, devices, layout_algorithm=layout_algorithm)

        # Создаем диаграмму DraeIO
        viz.create_drawio_diagram(objects)

    # Интерактивный запрос на конвертацию DRAWIO в YAML
    print("\n" + "=" * 60)
    convert_choice = input("Произвести конвертацию данных из drawio файла? (Y/N): ").strip().lower()

    if convert_choice in ('y', 'yes', 'д', 'да'):
        print("\n🔄 Конвертация DRAWIO в YAML...")

        if os.path.exists(DIAGRAM):
            try:
                converter = DrawioConverter()
                converter.convert_drawio_to_yaml(DIAGRAM, SEAF_YAML)
                print(f"✅ YAML файл успешно создан: {SEAF_YAML}")
            except Exception as e:
                sys.stderr.write(f"❌ Ошибка конвертации: {e}\n")
        else:
            sys.stderr.write(f"⚠️  Файл диаграммы не найден: {DIAGRAM}\n")
    else:
        print("\n⏭️  Конвертация пропущена")

    print("\n" + "=" * 60)
    print("Работа завершена")

if __name__ == "__main__":
    main()