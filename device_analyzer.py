# device_analyzer.py

import os
import re
import json
from typing import Dict, List, Any, Optional
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

def write_report_to_file(results, fname, conf_dir ):
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

            f.write("\n\n")

    print(f"✅ Детальная информация сохранена в файл: network_details.txt")
