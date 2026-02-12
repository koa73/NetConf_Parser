import os
from lib.device_analyzer import *
from lib.network_visualizer import NetworkVisualizer

CONFIG_DIR = "./data"
PATTERNS_DIR = "./patterns"
PATTERNS_DIR_DEV = os.path.join(PATTERNS_DIR, "devices")
DRAWIO_TEMPLATES = os.path.join(PATTERNS_DIR, "drawio")
STENCIL_TEMPLATES = os.path.join(DRAWIO_TEMPLATES, "templates")
REPORT = "network_details.txt"
DIAGRAM = "network_diagram.drawio"


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
    topology_analyzer = NetworkTopologyAnalyzer()
    links_result = topology_analyzer.analyze_topology(devices)

    # Генерация отчётов
    ReportGenerator.print_short_report(devices)
    ReportGenerator.print_topology_analysis(links_result)
    ReportGenerator.write_detailed_report(devices, REPORT, links_result, CONFIG_DIR)


    if links_result:
        print(f"⚠️  Создаю диаграмму\n")

        # Генерация сетевой диаграммы
        viz = NetworkVisualizer(
            pattern_dir = DRAWIO_TEMPLATES, drawio_template = DRAWIO_TEMPLATES + "/base.drawio",
            drawio_stencil_templates = STENCIL_TEMPLATES
        )

        # Выводим меню выбора алгоритма размещения
        print("Выберите алгоритм размещения объектов на диаграмме:")
        print("1. Круговой алгоритм (по умолчанию)")
        print("2. Сеточный алгоритм")
        print("3. Силовой алгоритм")
        print("4. Кластерный алгоритм")
        print("Нажмите Enter для выбора алгоритма по умолчанию (круговой)")
        
        choice = input("Введите номер алгоритма (1-4) или нажмите Enter: ").strip()
        
        # Определяем название алгоритма на основе выбора пользователя
        algorithm_map = {
            '1': 'circular',
            '2': 'grid',
            '3': 'force_directed',
            '4': 'clustered'
        }
        
        layout_algorithm = algorithm_map.get(choice, 'circular')  # По умолчанию круговой
        
        viz.prepare_stencils(links_result, layout_algorithm=layout_algorithm)

if __name__ == "__main__":
    main()