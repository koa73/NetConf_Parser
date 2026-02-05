# visualizer.py

import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import math

PRESENTATION_DIR = "../presentation"
TEMPLATES_DIR = os.path.join(PRESENTATION_DIR, "templates")

def load_drawio_template() -> str:
    """Загружает шаблон XML для draw.io из файла"""
    template_path = os.path.join(PRESENTATION_DIR, "drawio_template.xml")
    
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


def load_presentation_templates() -> Dict[str, Dict]:
    """Загружает шаблоны визуализации из каталога presentation/templates/"""
    templates = {}
    
    if not os.path.exists(TEMPLATES_DIR):
        raise FileNotFoundError(
            f"❌ Каталог с шаблонами визуализации не найден: {TEMPLATES_DIR}\n"
            f"💡 Создайте каталог и поместите в него файлы шаблонов:"
            f"\n   mkdir -p {TEMPLATES_DIR}"
            f"\n   # Затем создайте файлы шаблонов в этом каталоге"
        )
    
    for fname in os.listdir(TEMPLATES_DIR):
        if not fname.endswith(".json"):
            continue
        
        path = os.path.join(TEMPLATES_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                template = json.load(f)
                key = f"{template['vendor'].lower()}_{template['device_type'].lower()}"
                templates[key] = template
                print(f"🎨 Загружен шаблон визуализации: {fname}")
        except Exception as e:
            print(f"❌ Ошибка загрузки шаблона {fname}: {str(e)}")
    
    if not templates:
        raise Exception(
            f"❌ Не найдено ни одного шаблона визуализации в каталоге: {TEMPLATES_DIR}\n"
            f"💡 Пожалуйста, создайте хотя бы один файл шаблона (например, default.json)"
        )
    
    return templates


def extract_networks_from_device(device_info: Dict) -> List[Dict]:
    """Извлекает сети из конфигурации устройства для построения связей"""
    networks = []
    
    for net in device_info.get("routing_networks", []):
        if "interface" in net and "network" in net:
            interface = net["interface"]
            network = net["network"]
            
            # Извлекаем IP и маску
            parts = network.split('/')
            if len(parts) == 2:
                ip = parts[0]
                mask = parts[1]
                try:
                    prefix = int(mask)
                    networks.append({
                        "interface": interface,
                        "ip": ip,
                        "prefix": prefix,
                        "full_network": network
                    })
                except ValueError:
                    pass
    
    return networks


def find_connections(devices: List[Dict]) -> List[Dict]:
    """Находит связи между устройствами на основе общих сетей"""
    connections = []
    device_networks = {}
    
    # Собираем сети для каждого устройства
    for device in devices:
        networks = extract_networks_from_device(device)
        if networks:
            device_networks[device["filename"]] = {
                "device": device,
                "networks": networks
            }
    
    # Находим общие сети
    checked_pairs = set()
    device_list = list(device_networks.keys())
    
    for i in range(len(device_list)):
        for j in range(i + 1, len(device_list)):
            dev1_name = device_list[i]
            dev2_name = device_list[j]
            
            if (dev1_name, dev2_name) in checked_pairs:
                continue
            
            checked_pairs.add((dev1_name, dev2_name))
            
            dev1 = device_networks[dev1_name]
            dev2 = device_networks[dev2_name]
            
            # Поиск общих сетей
            for net1 in dev1["networks"]:
                for net2 in dev2["networks"]:
                    # Простая проверка на принадлежность к одной сети
                    if net1["full_network"] == net2["full_network"]:
                        connections.append({
                            "source": dev1["device"]["filename"],
                            "target": dev2["device"]["filename"],
                            "source_interface": net1["interface"],
                            "target_interface": net2["interface"],
                            "network": net1["full_network"]
                        })
    
    return connections


def generate_drawio_xml(devices: List[Dict], connections: List[Dict], templates: Dict) -> str:
    """Генерирует XML для draw.io на основе устройств и связей"""
    drawio_template = load_drawio_template()

    mx_cells = []
    cell_id = 2  # Начинаем с 2, так как 0 и 1 зарезервированы

    # Создаем узлы для устройств
    device_positions = {}
    device_cells = {}

    # Рассчитываем позиции устройств по кругу
    center_x, center_y = 600, 400
    radius = 300
    angle_step = 360 / max(1, len(devices))

    for i, device in enumerate(devices):
        # Определяем шаблон для устройства
        key = determine_device_key(device)
        template = templates.get(key)

        # Если нет конкретного шаблона, используем дефолтный
        if not template:
            template = templates.get("default_default")

        if not template:
            raise Exception(f"❌ Не найден шаблон для устройства {device['filename']} (ключ: {key})")

        # Рассчитываем позицию по кругу
        angle = math.radians(i * angle_step)
        x = center_x + radius * math.cos(angle) - template["width"] / 2
        y = center_y + radius * math.sin(angle) - template["height"] / 2

        # Формируем метку с заменой переменных
        label = template["default_label"]
        label = label.replace("${device_name}", device["device_name"])
        label = label.replace("${model}", device["model"])
        label = label.replace("${vendor}", device["vendor"])

        # Создаем XML-элемент для устройства
        style = template["style"]
        shape = template["shape"]

        cell = f"""
        <mxCell id="{cell_id}" value="{label}" style="{style}shape={shape};" parent="1" vertex="1">
          <mxGeometry x="{x}" y="{y}" width="{template['width']}" height="{template['height']}" as="geometry"/>
        </mxCell>"""

        mx_cells.append(cell)
        device_positions[device["filename"]] = (x, y, template["width"], template["height"])
        device_cells[device["filename"]] = cell_id
        cell_id += 1

    # Создаем соединения между устройствами
    for conn in connections:
        source_id = device_cells.get(conn["source"])
        target_id = device_cells.get(conn["target"])

        if source_id and target_id:
            # Рассчитываем точки соединения
            src_x, src_y, src_w, src_h = device_positions[conn["source"]]
            tgt_x, tgt_y, tgt_w, tgt_h = device_positions[conn["target"]]

            # Определяем точки соединения на границах устройств
            src_point = (src_x + src_w/2, src_y + src_h/2)
            tgt_point = (tgt_x + tgt_w/2, tgt_y + tgt_h/2)

            # Создаем XML-элемент для соединения
            edge_label = f"{conn['source_interface']} / {conn['target_interface']}\n{conn['network']}"

            edge = f"""
        <mxCell id="{cell_id}" value="{edge_label}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;fontSize=10;" parent="1" source="{source_id}" target="{target_id}" edge="1">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>"""

            mx_cells.append(edge)
            cell_id += 1

    # Формируем полный XML
    cells_xml = "".join(mx_cells)
    return drawio_template.format(cells_xml)


def generate_network_diagram(devices: List[Dict], output_file: str = "network_diagram.drawio"):
    """Основная функция генерации сетевой диаграммы"""
    print("\n🎨 Генерация сетевой диаграммы...")
    
    # Проверяем существование каталога presentation
    if not os.path.exists(PRESENTATION_DIR):
        raise FileNotFoundError(
            f"❌ Каталог с шаблонами presentation не найден: {PRESENTATION_DIR}\n"
            f"💡 Создайте каталог и поместите в него шаблоны:"
            f"\n   mkdir -p {PRESENTATION_DIR}"
            f"\n   mkdir -p {TEMPLATES_DIR}"
            f"\n   # Затем создайте файлы drawio_template.xml и шаблонов в этих каталогах"
        )
    
    # Загружаем шаблоны визуализации
    templates = load_presentation_templates()
    
    # Находим связи между устройствами
    connections = find_connections(devices)
    print(f"🔗 Найдено связей: {len(connections)}")
    
    # Генерируем XML для draw.io
    xml_content = generate_drawio_xml(devices, connections, templates)
    
    # Сохраняем в файл
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    print(f"✅ Диаграмма сохранена в файл: {output_file}")
    print(f"💡 Откройте файл в draw.io (https://app.diagrams.net/) для просмотра и редактирования")
    
    return output_file


def determine_device_key(device_info: Dict) -> str:
    """Определяет ключ для поиска шаблона на основе вендора и типа устройства"""
    vendor = device_info["vendor"].lower()
    device_type = device_info["device_type"].lower()
    
    # Упрощаем тип устройства для поиска шаблона
    simplified_type = "default"
    
    if vendor == "huawei":
        # Специальная обработка для Huawei с поиском по модели
        model = device_info.get("model", "").lower()
        if "fm8850" in model or "8850" in model:
            return "huawei_switch"
        if "ce6881" in model or "ce8850" in model or "ce6800" in model:
            return "huawei_switch"
        elif "ne" in model or "ar" in model:
            return "huawei_router"
    
    if "switch" in device_type.lower() or "leaf" in device_type.lower() or "spine" in device_type.lower():
        simplified_type = "switch"
    elif "router" in device_type.lower() or "core" in device_type.lower():
        simplified_type = "router"
    elif "firewall" in device_type.lower() or "security" in device_type.lower():
        simplified_type = "firewall"
    
    # Возвращаем ключ в формате "vendor_simplified_type"
    return f"{vendor}_{simplified_type}"