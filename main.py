# main.py

import os
import sys
from typing import List, Dict
from device_analyzer import PATTERNS_DIR, load_vendor_patterns, analyze_device_file

CONFIG_DIR = "./data"

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
        vendor_patterns = load_vendor_patterns()
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

    # Подготовка таблицы для вывода с улучшенным форматированием
    headers = ["Файл", "Вендор", "Имя", "Модель", "Тип", "VLAN", "Сети"]
    rows = []

    for r in results:
        # Улучшенное форматирование длинных имен файлов
        filename = r["filename"]
        if len(filename) > 35:
            filename = filename[:32] + "..."
        
        rows.append([
            filename,
            r["vendor"],
            r["device_name"] if r["device_name"] != "unknown" else "—",
            r["model"] if r["model"] != "unknown" else "—",
            r["device_type"],
            str(r["total_vlans"]),
            str(len(r["routing_networks"]))
        ])

    # Автоматическая ширина колонок
    col_widths = [
        max(len(str(row[i])) for row in [headers] + rows)
        for i in range(len(headers))
    ]

    def format_row(row_data):
        return "  ".join(str(item).ljust(col_widths[i]) for i, item in enumerate(row_data))

    # Вывод таблицы
    print("\n" + "=" * (sum(col_widths) + 2 * (len(col_widths) - 1)))
    print(format_row(headers))
    print("-" * (sum(col_widths) + 2 * (len(col_widths) - 1)))
    for row in rows:
        print(format_row(row))
    print("=" * (sum(col_widths) + 2 * (len(col_widths) - 1)) + "\n")

    # Сохранение подробной информации в файл
    with open("network_details.txt", "w", encoding='utf-8') as f:
        f.write(f"Анализ сетевого оборудования - {len(results)} устройств\n")
        f.write(f"Дата: {os.popen('date').read().strip()}\n")
        f.write("=" * 80 + "\n\n")
        
        for r in results:
            f.write(f"{'=' * 40}\n")
            f.write(f"Устройство: {r['filename']}\n")
            f.write(f"{'=' * 40}\n")
            f.write(f"Vendor: {r['vendor']}\n")
            f.write(f"Device Name: {r['device_name']}\n")
            f.write(f"Model: {r['model']}\n")
            f.write(f"Type: {r['device_type']}\n")
            f.write(f"Template Version: {r.get('template_version', 'unknown')}\n")
            f.write(f"Total VLANs: {r['total_vlans']}\n")
            f.write(f"Active VLANs: {', '.join(str(vlan) for vlan in r['active_vlans']) if r['active_vlans'] else 'None'}\n")
            f.write(f"Routing Networks Count: {len(r['routing_networks'])}\n")
            
            if r['routing_networks']:
                f.write("\nRouting Networks:\n")
                for i, net in enumerate(r["routing_networks"], 1):
                    if 'interface' in net:
                        f.write(f"  {i}. Interface: {net['interface']}, Network: {net['network']}\n")
                    elif 'route' in net:
                        f.write(f"  {i}. Static Route: {net['route']}\n")
            
            f.write("\nConfiguration snippet:\n")
            try:
                with open(os.path.join(CONFIG_DIR, r['filename']), 'r', encoding='utf-8', errors='ignore') as config_file:
                    lines = config_file.readlines()
                    for line in lines[:10]:  # Первые 10 строк конфигурации
                        f.write(f"  {line.rstrip()}\n")
            except Exception as e:
                f.write(f"  ⚠️ Не удалось прочитать конфигурацию: {str(e)}\n")
            
            f.write("\n\n")

    print(f"✅ Детальная информация сохранена в файл: network_details.txt")

if __name__ == "__main__":
    main()