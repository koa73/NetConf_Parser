# main.py (обновленная версия с визуализацией)

import os
import sys
from lib.device_analyzer import load_vendor_patterns, analyze_device_file, print_short_report, \
    write_report_to_file, analyze_network_topology, print_analysis_result

CONFIG_DIR = "./data"
PATTERNS_DIR = "./patterns"
REPORT = "network_details.txt"
DIAGRAM = "network_diagram.drawio"

def main():
    if not os.path.exists(CONFIG_DIR):
        print(f"⚠️  Создаю каталог для конфигов: {CONFIG_DIR}")
        os.makedirs(CONFIG_DIR)
        
    if not os.path.exists(PATTERNS_DIR):
        print(f"⚠️  Создаю каталог для шаблонов: {PATTERNS_DIR}")
        os.makedirs(PATTERNS_DIR)
        print("❗ Поместите шаблоны вендоров в каталог patterns/ и запустите скрипт снова")
        sys.exit(1)
    
    try:
        vendor_patterns = load_vendor_patterns(PATTERNS_DIR)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    if not vendor_patterns:
        print("❌ Не удалось загрузить ни одного шаблона. Завершение работы.")
        sys.exit(1)

    files = [f for f in os.listdir(CONFIG_DIR) if os.path.isfile(os.path.join(CONFIG_DIR, f))]
    if not files:
        print(f"📂 В каталоге '{CONFIG_DIR}' нет файлов для анализа.")
        return

    results = []
    for fname in files:
        full_path = os.path.join(CONFIG_DIR, fname)
        info = analyze_device_file(full_path, vendor_patterns)
        results.append(info)

    links = analyze_network_topology(results)

    # Вывод краткой информации
    print_short_report(results)
    print_analysis_result(links)

    # Запись данных в файл
    write_report_to_file(results, REPORT, links, CONFIG_DIR)

    # Генерация сетевой диаграммы
    if links:
        print(f"⚠️  Создаю диаграмму\n")
        #generate_network_diagram(results, DIAGRAM)
if __name__ == "__main__":
    main()