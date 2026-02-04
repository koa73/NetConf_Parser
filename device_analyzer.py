# device_analyzer.py

import os
import re
import json
from typing import List, Dict, Any, Tuple, Set, Optional
import ipaddress
from collections import Counter

PATTERNS_DIR = "./patterns"

def load_vendor_patterns() -> List[Dict[str, Any]]:
    if not os.path.isdir(PATTERNS_DIR):
        raise FileNotFoundError(f"Каталог шаблонов не найден: {PATTERNS_DIR}")
    
    patterns = []
    for fname in os.listdir(PATTERNS_DIR):
        if not fname.endswith(".json"):
            continue
            
        path = os.path.join(PATTERNS_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                pattern = json.load(f)
                pattern['_source_file'] = fname
                patterns.append(pattern)
                print(f"✅ Загружен шаблон: {fname} (версия {pattern.get('version', 'unknown')})")
        except Exception as e:
            print(f"❌ Ошибка в файле {fname}: {str(e)}")
    
    return patterns


def match_patterns(content_lines: List[str], patterns: List[str], case_insensitive: bool = True) -> bool:
    flags = re.IGNORECASE if case_insensitive else 0
    for line in content_lines:
        for pattern in patterns:
            if re.search(pattern, line, flags):
                return True
    return False


def extract_with_pattern(content_full: str, patterns: List[Dict], content_lines: List[str]) -> str:
    for p in patterns:
        if p.get("multiline", False):
            match = re.search(p["pattern"], content_full, re.IGNORECASE | re.DOTALL)
        else:
            match = None
            for line in content_lines:
                match = re.search(p["pattern"], line, re.IGNORECASE)
                if match:
                    break
        
        if match:
            value = match.group(p.get("group", 1)).strip()
            # Улучшенная очистка - сохраняем только буквы, цифры, точки, дефисы и подчеркивания
            if p.get("clean", True):
                value = re.sub(r'[^\w\.\-\_]', '', value).strip()
            # Если после очистки осталось пусто - пробуем без очистки
            if not value and p.get("fallback", False):
                value = match.group(p.get("group", 1)).strip()
            return value
    return "unknown"


def extract_model_with_fallback(content_full: str, patterns: List[Dict], content_lines: List[str], vendor: str) -> str:
    """Улучшенное извлечение модели с fallback-логикой для конкретных вендоров"""
    # Сначала пробуем основные паттерны
    model = extract_with_pattern(content_full, patterns, content_lines)
    
    if model != "unknown":
        return model
    
    # Fallback для Cisco Nexus
    if vendor == "Cisco":
        content_lower = content_full.lower()
        if "boot nxos" in content_lower:
            if "n9000" in content_lower or "9.3" in content_lower:
                return "Nexus 9000"
            elif "n7000" in content_lower or "7.0(3)i7(9)" in content_lower:
                return "Nexus 5000/6000"
            elif "n5000" in content_lower:
                return "Nexus 5000"
        if "asa" in content_lower or ": saved" in content_lower:
            return "ASA (Firewall)"
    
    # Fallback для Juniper
    elif vendor == "Juniper":
        content_lower = content_full.lower()
        if "qfx" in content_lower or "evpn" in content_lower or "vxlan" in content_lower:
            return "QFX Series (EVPN/VXLAN Switch)"
        elif "ex" in content_lower or "ethernet-switching" in content_lower:
            return "EX Series (Switch)"
        elif "srx" in content_lower or "security {" in content_lower:
            return "SRX Series (Firewall)"
        elif "mx" in content_lower or "mpls" in content_lower:
            return "MX Series (Router)"
    
    # Fallback для Huawei
    elif vendor == "Huawei":
        content_lower = content_full.lower()
        if "ce6881" in content_lower or "ce6881-48s6cq" in content_lower:
            return "CE6881-48S6CQ"
        elif "ce68" in content_lower or "ce88" in content_lower:
            return "CE Series (Data Center Switch)"
        elif "ne40" in content_lower or "ne80" in content_lower:
            return "NE Series (Carrier Router)"
        elif "s57" in content_lower or "s67" in content_lower:
            return "S Series (Enterprise Switch)"
        elif "ma56" in content_lower or "gpon" in content_lower:
            return "MA5600/MA5800 Series (OLT)"
        elif "firewall" in content_lower or "security-policy" in content_lower:
            return "USG Series (Firewall)"
    
    return "unknown"


def infer_type_by_features(content_lower: str, type_rules: List[Dict]) -> str:
    """Определяет тип устройства по наличию функций согласно правилам из шаблона."""
    best_type = "unknown"
    best_score = -1
    
    for rule in type_rules:
        score = rule.get("score", 1)
        matched = False
        
        if "any" in rule:
            # Совпадение с любым из паттернов
            for pat in rule["any"]:
                if pat.lower() in content_lower:
                    matched = True
                    break
        elif "all" in rule:
            # Совпадение со всеми паттернами
            matched = all(pat.lower() in content_lower for pat in rule["all"])
        
        if matched and score > best_score:
            best_score = score
            best_type = rule["type"]
    
    return best_type


def extract_networks_and_vlans_from_rules(
    content_full: str,
    content_lines: List[str],
    extraction_rules: Dict
) -> Dict[str, Any]:
    result = {
        "routing_networks": [],
        "total_vlans": 0,
        "active_vlans": [],
        "all_vlans": set()
    }
    
    # Извлечение интерфейсов с IP
    if "interfaces" in extraction_rules:
        current_interface = None
        interface_ip = None
        is_disabled = False
        
        for line in content_lines:
            iface_match = re.search(extraction_rules["interfaces"]["start"], line, re.IGNORECASE)
            if iface_match:
                if current_interface and interface_ip and not is_disabled:
                    result["routing_networks"].append({
                        "interface": current_interface,
                        "network": interface_ip
                    })
                current_interface = iface_match.group(1).strip()
                interface_ip = None
                is_disabled = False
                continue
            
            if current_interface and "ip_pattern" in extraction_rules["interfaces"]:
                ip_match = re.search(extraction_rules["interfaces"]["ip_pattern"], line, re.IGNORECASE)
                if ip_match:
                    try:
                        interface_ip = f"{ip_match.group(1)}/{ip_match.group(2)}"
                    except IndexError:
                        interface_ip = ip_match.group(1)
            
            if current_interface and "disable_pattern" in extraction_rules["interfaces"]:
                if re.search(extraction_rules["interfaces"]["disable_pattern"], line, re.IGNORECASE):
                    is_disabled = True
        
        if current_interface and interface_ip and not is_disabled:
            result["routing_networks"].append({
                "interface": current_interface,
                "network": interface_ip
            })
    
    # Извлечение VLAN
    if "vlans" in extraction_rules:
        vlan_set = set()
        active_set = set()
        
        for line in content_lines:
            if "all_pattern" in extraction_rules["vlans"]:
                for match in re.finditer(extraction_rules["vlans"]["all_pattern"], line, re.IGNORECASE):
                    try:
                        vid = int(match.group(1))
                        vlan_set.add(vid)
                    except (ValueError, IndexError):
                        pass
            
            if "active_pattern" in extraction_rules["vlans"]:
                for match in re.finditer(extraction_rules["vlans"]["active_pattern"], line, re.IGNORECASE):
                    try:
                        vid = int(match.group(1))
                        active_set.add(vid)
                        vlan_set.add(vid)
                    except (ValueError, IndexError):
                        pass
        
        result["all_vlans"] = sorted(vlan_set)
        result["active_vlans"] = sorted(active_set)
        result["total_vlans"] = len(vlan_set)
    
    return result


def detect_vendor_and_model(content: str, vendor_patterns: List[Dict]) -> Optional[Dict[str, str]]:
    content_lines = [line.rstrip() for line in content.splitlines() if line.strip()]
    content_full = content.replace('\r', '')
    content_lower = content_full.lower()

    # Этап 1: определение вендора по уникальным сигнатурам
    vendor_scores = Counter()
    for pattern in vendor_patterns:
        vendor = pattern["vendor"]
        signatures = pattern.get("vendor_signatures", [])
        if signatures:
            score = sum(
                any(re.search(sig, line, re.IGNORECASE) for line in content_lines)
                for sig in signatures
            )
            if score > 0:
                vendor_scores[vendor] = score
    
    if not vendor_scores:
        for pattern in vendor_patterns:
            if match_patterns(content_lines, pattern.get("detect_patterns", [])):
                vendor_scores[pattern["vendor"]] = 1
                break
    
    if not vendor_scores:
        return None
    
    matched_vendor = vendor_scores.most_common(1)[0][0]
    pattern = next(p for p in vendor_patterns if p["vendor"] == matched_vendor)

    # Этап 2: извлечение данных по шаблону
    device_name = extract_with_pattern(content_full, pattern.get("name_patterns", []), content_lines)
    model = extract_model_with_fallback(content_full, pattern.get("model_patterns", []), content_lines, matched_vendor)

    # Этап 3: определение типа по функциям
    device_type = "unknown"
    if "type_inference" in pattern:
        device_type = infer_type_by_features(content_lower, pattern["type_inference"])
    if device_type == "unknown":
        device_type = pattern.get("default_device_type", "unknown")

    # Этап 4: извлечение сетей и VLAN по правилам из шаблона
    network_extraction_rules = pattern.get("network_extraction_rules", {})
    network_info = extract_networks_and_vlans_from_rules(content_full, content_lines, network_extraction_rules)

    return {
        "vendor": matched_vendor,
        "device_name": device_name,
        "model": model,
        "device_type": device_type,
        **network_info
    }

def analyze_device_file(filepath: str, vendor_patterns: List[Dict]) -> Dict[str, Any]:
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return {
            "filename": filename,
            "vendor": "error",
            "device_name": "failed_to_read",
            "model": "failed_to_read",
            "device_type": "unknown",
            "routing_networks": [],
            "total_vlans": 0,
            "active_vlans": [],
            "all_vlans": []
        }

    result = detect_vendor_and_model(content, vendor_patterns)
    if result:
        return {
            "filename": filename,
            **result
        }
    else:
        return {
            "filename": filename,
            "vendor": "unknown",
            "device_name": "unknown",
            "model": "unknown",
            "device_type": "unknown",
            "routing_networks": [],
            "total_vlans": 0,
            "active_vlans": [],
            "all_vlans": []
        }

def print_short_report(results):

    # Подготовка таблицы для вывода
    headers = ["Файл", "Вендор", "Имя", "Модель", "Тип", "VLAN", "Сети"]
    rows = []

    for r in results:
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

def write_report_to_file(results, fname,  links_result, conf_dir ):
    # Сохранение подробной информации в файл
    with open(fname, "w", encoding='utf-8') as f:
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
            f.write(f"Total VLANs: {r['total_vlans']}\n")
            f.write(
                f"Active VLANs: {', '.join(str(vlan) for vlan in r['active_vlans']) if r['active_vlans'] else 'None'}\n")
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
                with open(os.path.join(conf_dir, r['filename']), 'r', encoding='utf-8',
                          errors='ignore') as config_file:
                    lines = config_file.readlines()
                    for line in lines[:10]:
                        f.write(f"  {line.rstrip()}\n")
            except Exception as e:
                f.write(f"  ⚠️ Не удалось прочитать конфигурацию: {str(e)}\n")

            f.write("\n")

        links = links_result.get("physical_links", [])

        if not links:
            f.write("⚠️  Физические связи не обнаружены\n")
            return

        f.write("### Таблица связей между устройствами\n")
        f.write("\n" + "=" * 150 + "\n")
        f.write(f"{'Устройство 1':<25} | {'Интерфейс':<18} | {'IP':<16} | "
              f"{'Устройство 2':<25} | {'Интерфейс':<18} | {'IP':<16} | {'Сеть':<20}\n")
        f.write("=" * 150 + "\n")

        for link in links:
            dev1, intf1, ip1, dev2, intf2, ip2, net = link
            f.write(f"{dev1:<25} | {intf1:<18} | {ip1:<16} | "
                  f"{dev2:<25} | {intf2:<18} | {ip2:<16} | {net:<20}" + "\n")

        f.write("=" * 150 + "\n")
        f.write(f"Всего обнаружено физических связей: {len(links)}\n")

        f.write("\n\n")

    print(f"✅ Детальная информация сохранена в файл: network_details.txt")

def netmask_to_prefix(netmask: str) -> int:
    """Преобразует маску из dotted-decimal в префикс."""
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
    except ValueError as e:
        raise ValueError(f"Некорректная маска '{netmask}': {e}")


def calculate_network_address(ip_str: str, netmask_str: str) -> str:
    """Вычисляет сетевой адрес в CIDR формате."""
    prefix = netmask_to_prefix(netmask_str)
    network = ipaddress.IPv4Network(f"{ip_str}/{prefix}", strict=False)
    return str(network)


def parse_interface_network(network_entry: str) -> Dict[str, Any]:
    """Парсит запись сети интерфейса."""
    ip_str, netmask_str = network_entry.split('/')
    prefix = netmask_to_prefix(netmask_str)
    network_cidr = calculate_network_address(ip_str, netmask_str)

    return {
        'ip': ip_str,
        'prefix': prefix,
        'network_cidr': network_cidr,
        'is_loopback': prefix == 32,
        'is_mgmt_network': netmask_str in ('255.255.255.0', '255.255.254.0', '255.255.252.0'),
        'is_p2p': prefix in (31, 30)
    }


def is_physical_interface(interface_name: str) -> bool:
    """Определяет физический интерфейс (не управленческий/VLAN/Bridge)."""
    non_physical = ('MEth', 'Vbdif', 'Vlanif', 'LoopBack', 'NULL')
    return not any(interface_name.startswith(prefix) for prefix in non_physical)


def is_mgmt_interface(interface_name: str, is_mgmt_network: bool) -> bool:
    """Определяет управленческий интерфейс."""
    mgmt_indicators = ('MEth', 'Vbdif1360837')
    return (any(interface_name.startswith(prefix) for prefix in mgmt_indicators) or
            (is_mgmt_network and interface_name.startswith('Vbdif')))


def extract_interface_number(interface_name: str) -> Tuple[str, List[int]]:
    """
    Извлекает базовое имя интерфейса и номера подынтерфейсов/VLAN.
    Примеры:
      '100GE1/0/61.1700' -> ('100GE1/0/61', [1700])
      '10GE1/0/46' -> ('10GE1/0/46', [])
    """
    match = re.match(r'^([^\d]*[\d/]+)(?:\.(\d+))?$', interface_name)
    if not match:
        return interface_name, []

    base = match.group(1)
    subif = [int(match.group(2))] if match.group(2) else []
    return base, subif


def extract_device_interfaces(device: Dict[str, Any],
                              filter_type: str = 'all') -> List[Dict[str, Any]]:
    """
    Извлекает интерфейсы устройства с фильтрацией по типу.

    Args:
        device: Словарь устройства
        filter_type: 'physical', 'mgmt', 'logical', 'all'

    Returns:
        Список интерфейсов с метаданными
    """
    interfaces = []

    for intf in device.get('routing_networks', []):
        interface_name = intf['interface']
        network_str = intf['network']

        parsed = parse_interface_network(network_str)
        base_intf, subif_numbers = extract_interface_number(interface_name)

        intf_data = {
            'interface': interface_name,
            'base_interface': base_intf,
            'subif_numbers': subif_numbers,
            'ip': parsed['ip'],
            'prefix': parsed['prefix'],
            'network_cidr': parsed['network_cidr'],
            'is_physical': is_physical_interface(interface_name),
            'is_mgmt': is_mgmt_interface(interface_name, parsed['is_mgmt_network']),
            'is_loopback': parsed['is_loopback'],
            'is_p2p': parsed['is_p2p']
        }

        # Фильтрация
        if filter_type == 'physical':
            if not (intf_data['is_physical'] and intf_data['is_p2p'] and not intf_data['is_loopback']):
                continue
        elif filter_type == 'mgmt':
            if not (intf_data['is_mgmt'] and not intf_data['is_loopback']):
                continue
        elif filter_type == 'logical':
            # Логические связи: сервисные сети (VBDIF), подынтерфейсы с номерами
            if (intf_data['is_loopback'] or
                    intf_data['is_mgmt'] or
                    (intf_data['is_physical'] and intf_data['is_p2p'])):
                continue

        interfaces.append(intf_data)

    return interfaces


def find_physical_links(devices_data: List[Dict[str, Any]]) -> List[List[str]]:
    """Выявляет физические P2P связи через /31 и /30 сети."""
    # Собираем физические интерфейсы
    device_interfaces: Dict[str, List[Dict[str, Any]]] = {}
    for device in devices_data:
        device_name = device['device_name']
        device_interfaces[device_name] = extract_device_interfaces(device, filter_type='physical')

    # Индексируем сети
    network_index: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for device_name, interfaces in device_interfaces.items():
        for intf in interfaces:
            net = intf['network_cidr']
            network_index.setdefault(net, []).append((device_name, intf))

    # Формируем связи (только сети с ровно 2 устройствами)
    links = []
    processed_pairs: Set[Tuple[str, str, str]] = set()

    for network_cidr, endpoints in network_index.items():
        if len(endpoints) != 2:
            continue

        dev1_name, intf1 = endpoints[0]
        dev2_name, intf2 = endpoints[1]

        pair_key = tuple(sorted([dev1_name, dev2_name]) + [network_cidr])
        if pair_key in processed_pairs:
            continue

        processed_pairs.add(pair_key)
        links.append([
            dev1_name,
            intf1['interface'],
            intf1['ip'],
            dev2_name,
            intf2['interface'],
            intf2['ip'],
            network_cidr
        ])

    return links


def find_mgmt_interfaces(devices_data: List[Dict[str, Any]]) -> List[List[str]]:
    """Извлекает управленческие интерфейсы."""
    mgmt_interfaces = []

    for device in devices_data:
        device_name = device['device_name']
        mgmt_ifs = extract_device_interfaces(device, filter_type='mgmt')

        for intf in mgmt_ifs:
            mgmt_interfaces.append([
                device_name,
                intf['interface'],
                intf['ip'],
                intf['network_cidr']
            ])

    mgmt_interfaces.sort(key=lambda x: (x[3], x[0]))
    return mgmt_interfaces


def find_logical_links(devices_data: List[Dict[str, Any]]) -> List[List[str]]:
    """
    Выявляет логические связи:
    1. Общие сервисные сети (VBDIF) между устройствами
    2. VXLAN overlay через подынтерфейсы с одинаковыми номерами VNI
    3. Логические P2P через /30 сети (не физические)
    """
    logical_links = []
    processed_networks: Set[str] = set()
    processed_vni_pairs: Set[Tuple[str, str, int]] = set()

    # Собираем все интерфейсы для анализа
    all_interfaces: Dict[str, List[Dict[str, Any]]] = {}
    for device in devices_data:
        device_name = device['device_name']
        all_interfaces[device_name] = extract_device_interfaces(device, filter_type='all')

    # === 1. Общие сервисные сети (VBDIF) ===
    network_to_devices: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for device_name, interfaces in all_interfaces.items():
        for intf in interfaces:
            # Фильтруем только сервисные интерфейсы (VBDIF/Vlanif) с масками /24-/28
            if (intf['interface'].startswith(('Vbdif', 'Vlanif')) and
                    24 <= intf['prefix'] <= 28 and
                    not intf['is_loopback']):
                net = intf['network_cidr']
                network_to_devices.setdefault(net, []).append((device_name, intf))

    # Формируем логические связи для сетей с 2+ устройствами
    for network_cidr, endpoints in network_to_devices.items():
        if len(endpoints) < 2 or network_cidr in processed_networks:
            continue

        processed_networks.add(network_cidr)

        # Создаем связи между всеми парами устройств в сети
        for i in range(len(endpoints)):
            for j in range(i + 1, len(endpoints)):
                dev1_name, intf1 = endpoints[i]
                dev2_name, intf2 = endpoints[j]

                logical_links.append([
                    dev1_name,
                    f"{intf1['interface']}/{intf1['ip']}",
                    dev2_name,
                    f"{intf2['interface']}/{intf2['ip']}",
                    f"Service Network: {network_cidr}"
                ])

    # === 2. VXLAN overlay через подынтерфейсы (эвристика по номерам VNI) ===
    vni_map: Dict[int, List[Tuple[str, Dict[str, Any]]]] = {}
    for device_name, interfaces in all_interfaces.items():
        for intf in interfaces:
            # Ищем подынтерфейсы с номерами (часто соответствуют VNI)
            if intf['subif_numbers'] and intf['base_interface'].startswith(('100GE', '40GE', '10GE')):
                vni = intf['subif_numbers'][0]
                # Фильтруем реалистичные VNI диапазоны (1000-16777215)
                if 1000 <= vni <= 16777215:
                    vni_map.setdefault(vni, []).append((device_name, intf))

    # Формируем логические связи для одинаковых VNI
    for vni, endpoints in vni_map.items():
        if len(endpoints) < 2:
            continue

        # Группируем по базовому интерфейсу для уточнения топологии
        base_intf_groups: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
        for dev_name, intf in endpoints:
            base_intf_groups.setdefault(intf['base_interface'], []).append((dev_name, intf))

        # Создаем связи внутри каждой группы базовых интерфейсов
        for base_intf, group_endpoints in base_intf_groups.items():
            if len(group_endpoints) < 2:
                continue

            for i in range(len(group_endpoints)):
                for j in range(i + 1, len(group_endpoints)):
                    dev1_name, intf1 = group_endpoints[i]
                    dev2_name, intf2 = group_endpoints[j]

                    pair_key = (min(dev1_name, dev2_name), max(dev1_name, dev2_name), vni)
                    if pair_key in processed_vni_pairs:
                        continue

                    processed_vni_pairs.add(pair_key)

                    logical_links.append([
                        dev1_name,
                        f"{intf1['interface']}/{intf1['ip']}",
                        dev2_name,
                        f"{intf2['interface']}/{intf2['ip']}",
                        f"VXLAN VNI {vni} (Overlay)"
                    ])

    # === 3. Логические P2P через /30 (не физические интерфейсы) ===
    p2p30_networks: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for device_name, interfaces in all_interfaces.items():
        for intf in interfaces:
            if (intf['prefix'] == 30 and
                    not intf['is_loopback'] and
                    not (intf['is_physical'] and intf['interface'].startswith(('100GE', '40GE')))):
                net = intf['network_cidr']
                p2p30_networks.setdefault(net, []).append((device_name, intf))

    for network_cidr, endpoints in p2p30_networks.items():
        if len(endpoints) != 2 or network_cidr in processed_networks:
            continue

        processed_networks.add(network_cidr)
        dev1_name, intf1 = endpoints[0]
        dev2_name, intf2 = endpoints[1]

        logical_links.append([
            dev1_name,
            f"{intf1['interface']}/{intf1['ip']}",
            dev2_name,
            f"{intf2['interface']}/{intf2['ip']}",
            f"Logical P2P: {network_cidr}"
        ])

    return logical_links


def analyze_network_topology(devices_data: List[Dict[str, Any]]) -> Dict[str, List[List[str]]]:
    """
    Полный анализ сетевой топологии.

    Возвращает словарь:
    {
        "physical_links": [[dev1, intf1, ip1, dev2, intf2, ip2, network], ...],
        "mgmt_networks": [[device, interface, ip, network], ...],
        "logical_links": [[dev1, intf/ip1, dev2, intf/ip2, description], ...]
    }
    """
    return {
        "physical_links": find_physical_links(devices_data),
        "mgmt_networks": find_mgmt_interfaces(devices_data),
        "logical_links": find_logical_links(devices_data)
    }


def print_analysis_result(result: Dict[str, List[List[str]]]) -> None:
    """Печатает результаты анализа в структурированном виде."""

    # Физические связи
    links = result.get("physical_links", [])
    print("\n" + "=" * 150)
    print(" 🔗 ФИЗИЧЕСКИЕ СВЯЗИ (Physical P2P Links)")
    print("=" * 150)
    if links:
        print(f"{'Устройство 1':<25} | {'Интерфейс':<18} | {'IP':<16} | "
              f"{'Устройство 2':<25} | {'Интерфейс':<18} | {'IP':<16} | {'Сеть':<20}")
        print("-" * 150)
        for link in links:
            dev1, intf1, ip1, dev2, intf2, ip2, net = link
            print(f"{dev1:<25} | {intf1:<18} | {ip1:<16} | "
                  f"{dev2:<25} | {intf2:<18} | {ip2:<16} | {net:<20}")
        print(f"\n✅ Всего физических связей: {len(links)}")
    else:
        print("⚠️  Физические связи не обнаружены")

    # Управленческие сети
    mgmt = result.get("mgmt_networks", [])
    print("\n" + "=" * 100)
    print(" 🖥️  УПРАВЛЕНЧЕСКИЕ ИНТЕРФЕЙСЫ (Management Networks)")
    print("=" * 100)
    if mgmt:
        print(f"{'Устройство':<25} | {'Интерфейс':<18} | {'IP адрес':<16} | {'Сеть':<20}")
        print("-" * 100)
        for entry in mgmt:
            dev, intf, ip, net = entry
            print(f"{dev:<25} | {intf:<18} | {ip:<16} | {net:<20}")
        print(f"\n✅ Всего управленческих интерфейсов: {len(mgmt)}")

        # Группировка по сетям
        networks = {}
        for entry in mgmt:
            net = entry[3]
            networks.setdefault(net, []).append(f"{entry[0]} ({entry[2]})")

        print("\nГруппировка по сетям управления:")
        for net, devices in sorted(networks.items()):
            print(f"  • {net}: {', '.join(devices)}")
    else:
        print("⚠️  Управленческие интерфейсы не обнаружены")

    # Логические связи
    logical = result.get("logical_links", [])
    print("\n" + "=" * 130)
    print(" 🌐 ЛОГИЧЕСКИЕ СВЯЗИ (Logical Links: VXLAN Overlay, Service Networks)")
    print("=" * 130)
    if logical:
        print(
            f"{'Устройство 1':<25} | {'Интерфейс/IP':<25} | {'Устройство 2':<25} | {'Интерфейс/IP':<25} | {'Тип связи':<35}")
        print("-" * 130)
        for link in logical:
            dev1, intf_ip1, dev2, intf_ip2, desc = link
            print(f"{dev1:<25} | {intf_ip1:<25} | {dev2:<25} | {intf_ip2:<25} | {desc:<35}")
        print(f"\n✅ Всего логических связей: {len(logical)}")

        # Статистика по типам
        vxlan_count = sum(1 for l in logical if 'VXLAN' in l[4])
        service_count = sum(1 for l in logical if 'Service Network' in l[4])
        p2p_count = sum(1 for l in logical if 'Logical P2P' in l[4])

        print("\nСтатистика логических связей:")
        if vxlan_count:
            print(f"  • VXLAN Overlay (VNI): {vxlan_count}")
        if service_count:
            print(f"  • Сервисные сети (L3): {service_count}")
        if p2p_count:
            print(f"  • Логические P2P (/30): {p2p_count}")
    else:
        print("ℹ️  Логические связи не обнаружены (требуется дополнительная информация о конфигурации тоннелей)")

    print("=" * 130 + "\n")
