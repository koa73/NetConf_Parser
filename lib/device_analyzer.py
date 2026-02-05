"""
Модуль анализа сетевого оборудования и топологии
"""
import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set, Optional, Union
import ipaddress
from collections import Counter


class VendorPatternLoader:
    """Загрузчик шаблонов распознавания вендоров из JSON-файлов."""

    def __init__(self, patterns_dir: Union[str, Path]):
        self.patterns_dir = Path(patterns_dir).resolve()
        self.patterns: List[Dict[str, Any]] = []

    def load_patterns(self) -> List[Dict[str, Any]]:
        """Загружает все шаблоны из каталога."""
        if not self.patterns_dir.exists():
            sys.stderr.write(f"❌ Каталог шаблонов не найден: {self.patterns_dir}\n")
            sys.exit(1)

        self.patterns = []
        for filepath in self.patterns_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    pattern = json.load(f)
                    pattern['_source_file'] = filepath.name
                    self.patterns.append(pattern)
                    print(
                        f"✅ Загружен шаблон: {filepath.name} "
                        f"(версия {pattern.get('version', 'unknown')})"
                    )
            except Exception as e:
                sys.stderr.write(f"❌ Ошибка в файле {filepath.name}: {e}\n")
                sys.exit(1)

        if not self.patterns:
            sys.stderr.write(f"⚠️  В каталоге {self.patterns_dir} не найдено шаблонов (*.json)\n")
            sys.exit(1)

        return self.patterns


class NetworkDevice:
    """Представление сетевого устройства с методами анализа конфигурации."""

    def __init__(self, filepath: Union[str, Path], vendor_patterns: List[Dict[str, Any]]):
        self.filepath = Path(filepath).resolve()
        self.filename = self.filepath.name
        self.vendor_patterns = vendor_patterns
        self.content: str = ""
        self.content_lines: List[str] = []
        self.content_lower: str = ""
        self.vendor: str = "unknown"
        self.device_name: str = "unknown"
        self.model: str = "unknown"
        self.device_type: str = "unknown"
        self.routing_networks: List[Dict[str, str]] = []
        self.total_vlans: int = 0
        self.active_vlans: List[int] = []
        self.all_vlans: List[int] = []

    def load_content(self) -> bool:
        """Загружает содержимое конфигурационного файла."""
        try:
            with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
                self.content = f.read()
            self.content_lines = [line.rstrip() for line in self.content.splitlines() if line.strip()]
            self.content_lower = self.content.lower()
            return True
        except Exception as e:
            sys.stderr.write(f"❌ Ошибка чтения файла {self.filename}: {e}\n")
            return False

    def _match_patterns(self, patterns: List[str], case_insensitive: bool = True) -> bool:
        """Проверяет совпадение любого паттерна с содержимым файла."""
        flags = re.IGNORECASE if case_insensitive else 0
        for line in self.content_lines:
            for pattern in patterns:
                if re.search(pattern, line, flags):
                    return True
        return False

    def _extract_with_pattern(self, patterns: List[Dict]) -> str:
        """Извлекает значение по списку паттернов."""
        for p in patterns:
            if p.get("multiline", False):
                match = re.search(p["pattern"], self.content, re.IGNORECASE | re.DOTALL)
            else:
                match = None
                for line in self.content_lines:
                    match = re.search(p["pattern"], line, re.IGNORECASE)
                    if match:
                        break

            if match:
                value = match.group(p.get("group", 1)).strip()
                if p.get("clean", True):
                    value = re.sub(r'[^\w.\-_]', '', value).strip()
                if not value and p.get("fallback", False):
                    value = match.group(p.get("group", 1)).strip()
                return value
        return "unknown"

    def _extract_model_with_fallback(self, patterns: List[Dict], vendor: str) -> str:
        """Извлекает модель с fallback-логикой для конкретных вендоров."""
        model = self._extract_with_pattern(patterns)
        if model != "unknown":
            return model

        # Fallback для специфических вендоров
        if vendor == "Cisco":
            if "boot nxos" in self.content_lower:
                if "n9000" in self.content_lower or "9.3" in self.content_lower:
                    return "Nexus 9000"
                elif "n7000" in self.content_lower:
                    return "Nexus 5000/6000"
                elif "n5000" in self.content_lower:
                    return "Nexus 5000"
            if "asa" in self.content_lower or ": saved" in self.content_lower:
                return "ASA (Firewall)"

        elif vendor == "Juniper":
            if "qfx" in self.content_lower or "evpn" in self.content_lower or "vxlan" in self.content_lower:
                return "QFX Series (EVPN/VXLAN Switch)"
            elif "ex" in self.content_lower or "ethernet-switching" in self.content_lower:
                return "EX Series (Switch)"
            elif "srx" in self.content_lower or "security {" in self.content_lower:
                return "SRX Series (Firewall)"
            elif "mx" in self.content_lower or "mpls" in self.content_lower:
                return "MX Series (Router)"

        elif vendor == "Huawei":
            if "ce6881" in self.content_lower:
                return "CE6881-48S6CQ"
            elif "ce68" in self.content_lower or "ce88" in self.content_lower:
                return "CE Series (Data Center Switch)"
            elif "ne40" in self.content_lower or "ne80" in self.content_lower:
                return "NE Series (Carrier Router)"
            elif "s57" in self.content_lower or "s67" in self.content_lower:
                return "S Series (Enterprise Switch)"
            elif "ma56" in self.content_lower or "gpon" in self.content_lower:
                return "MA5600/MA5800 Series (OLT)"
            elif "firewall" in self.content_lower or "security-policy" in self.content_lower:
                return "USG Series (Firewall)"

        return "unknown"

    def _infer_type_by_features(self, type_rules: List[Dict]) -> str:
        """Определяет тип устройства по наличию функций."""
        best_type = "unknown"
        best_score = -1
        for rule in type_rules:
            score = rule.get("score", 1)
            matched = False

            if "any" in rule:
                matched = any(pat.lower() in self.content_lower for pat in rule["any"])
            elif "all" in rule:
                matched = all(pat.lower() in self.content_lower for pat in rule["all"])

            if matched and score > best_score:
                best_score = score
                best_type = rule["type"]

        return best_type

    def _extract_networks_and_vlans(self, rules: Dict) -> Dict[str, Any]:
        """Извлекает сети и VLAN согласно правилам шаблона."""
        result = {
            "routing_networks": [],
            "total_vlans": 0,
            "active_vlans": [],
            "all_vlans": set()
        }

        # Извлечение интерфейсов с IP
        if "interfaces" in rules:
            current_interface = None
            interface_ip = None
            is_disabled = False

            for line in self.content_lines:
                iface_match = re.search(rules["interfaces"]["start"], line, re.IGNORECASE)
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

                if current_interface and "ip_pattern" in rules["interfaces"]:
                    ip_match = re.search(rules["interfaces"]["ip_pattern"], line, re.IGNORECASE)
                    if ip_match:
                        try:
                            interface_ip = f"{ip_match.group(1)}/{ip_match.group(2)}"
                        except IndexError:
                            interface_ip = ip_match.group(1)

                if current_interface and "disable_pattern" in rules["interfaces"]:
                    if re.search(rules["interfaces"]["disable_pattern"], line, re.IGNORECASE):
                        is_disabled = True

            if current_interface and interface_ip and not is_disabled:
                result["routing_networks"].append({
                    "interface": current_interface,
                    "network": interface_ip
                })

        # Извлечение VLAN
        if "vlans" in rules:
            vlan_set = set()
            active_set = set()

            for line in self.content_lines:
                if "all_pattern" in rules["vlans"]:
                    for match in re.finditer(rules["vlans"]["all_pattern"], line, re.IGNORECASE):
                        try:
                            vid = int(match.group(1))
                            vlan_set.add(vid)
                        except (ValueError, IndexError):
                            pass

                if "active_pattern" in rules["vlans"]:
                    for match in re.finditer(rules["vlans"]["active_pattern"], line, re.IGNORECASE):
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

    def analyze(self) -> bool:
        """Выполняет полный анализ конфигурации устройства."""
        if not self.load_content():
            return False

        # Этап 1: Определение вендора
        vendor_scores = Counter()
        for pattern in self.vendor_patterns:
            vendor = pattern["vendor"]
            signatures = pattern.get("vendor_signatures", [])
            if signatures:
                score = sum(
                    any(re.search(sig, line, re.IGNORECASE) for line in self.content_lines)
                    for sig in signatures
                )
                if score > 0:
                    vendor_scores[vendor] = score

        if not vendor_scores:
            for pattern in self.vendor_patterns:
                if self._match_patterns(pattern.get("detect_patterns", [])):
                    vendor_scores[pattern["vendor"]] = 1
                    break

        if not vendor_scores:
            return False

        self.vendor = vendor_scores.most_common(1)[0][0]
        pattern = next(p for p in self.vendor_patterns if p["vendor"] == self.vendor)

        # Этап 2: Извлечение данных
        self.device_name = self._extract_with_pattern(pattern.get("name_patterns", []))
        self.model = self._extract_model_with_fallback(pattern.get("model_patterns", []), self.vendor)

        # Этап 3: Определение типа
        if "type_inference" in pattern:
            self.device_type = self._infer_type_by_features(pattern["type_inference"])
        if self.device_type == "unknown":
            self.device_type = pattern.get("default_device_type", "unknown")

        # Этап 4: Извлечение сетей и VLAN
        rules = pattern.get("network_extraction_rules", {})
        network_info = self._extract_networks_and_vlans(rules)
        self.routing_networks = network_info["routing_networks"]
        self.total_vlans = network_info["total_vlans"]
        self.active_vlans = network_info["active_vlans"]
        self.all_vlans = network_info["all_vlans"]

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Возвращает результаты анализа в виде словаря."""
        return {
            "filename": self.filename,
            "vendor": self.vendor,
            "device_name": self.device_name,
            "model": self.model,
            "device_type": self.device_type,
            "routing_networks": self.routing_networks,
            "total_vlans": self.total_vlans,
            "active_vlans": self.active_vlans,
            "all_vlans": self.all_vlans
        }


class NetworkTopologyAnalyzer:
    """Анализатор сетевой топологии на основе данных об устройствах."""

    @staticmethod
    def netmask_to_prefix(netmask: str) -> int:
        """Преобразует маску из dotted-decimal в префикс."""
        try:
            return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
        except ValueError as e:
            raise ValueError(f"Некорректная маска '{netmask}': {e}")

    @staticmethod
    def calculate_network_address(ip_str: str, netmask_str: str) -> str:
        """Вычисляет сетевой адрес в CIDR формате."""
        prefix = NetworkTopologyAnalyzer.netmask_to_prefix(netmask_str)
        network = ipaddress.IPv4Network(f"{ip_str}/{prefix}", strict=False)
        return str(network)

    @staticmethod
    def parse_interface_network(network_entry: str) -> Dict[str, Any]:
        """Парсит запись сети интерфейса."""
        ip_str, netmask_str = network_entry.split('/')
        prefix = NetworkTopologyAnalyzer.netmask_to_prefix(netmask_str)
        network_cidr = NetworkTopologyAnalyzer.calculate_network_address(ip_str, netmask_str)
        return {
            'ip': ip_str,
            'prefix': prefix,
            'network_cidr': network_cidr,
            'is_loopback': prefix == 32,
            'is_mgmt_network': netmask_str in ('255.255.255.0', '255.255.254.0', '255.255.252.0'),
            'is_p2p': prefix in (31, 30)
        }

    @staticmethod
    def is_physical_interface(interface_name: str) -> bool:
        """Определяет физический интерфейс."""
        non_physical = ('MEth', 'Vbdif', 'Vlanif', 'LoopBack', 'NULL')
        return not any(interface_name.startswith(prefix) for prefix in non_physical)

    @staticmethod
    def is_mgmt_interface(interface_name: str, is_mgmt_network: bool) -> bool:
        """Определяет управленческий интерфейс."""
        mgmt_indicators = ('MEth', 'Vbdif1360837')
        return (any(interface_name.startswith(prefix) for prefix in mgmt_indicators) or
                (is_mgmt_network and interface_name.startswith('Vbdif')))

    @staticmethod
    def extract_interface_number(interface_name: str) -> Tuple[str, List[int]]:
        """Извлекает базовое имя интерфейса и номера подынтерфейсов."""
        match = re.match(r'^([^\d]*[\d/]+)(?:\.(\d+))?$', interface_name)
        if not match:
            return interface_name, []
        base = match.group(1)
        subif = [int(match.group(2))] if match.group(2) else []
        return base, subif

    @staticmethod
    def extract_device_interfaces(device: Dict[str, Any], filter_type: str = 'all') -> List[Dict[str, Any]]:
        """Извлекает интерфейсы устройства с фильтрацией по типу."""
        interfaces = []

        for intf in device.get('routing_networks', []):
            interface_name = intf['interface']
            network_str = intf['network']

            parsed = NetworkTopologyAnalyzer.parse_interface_network(network_str)
            base_intf, subif_numbers = NetworkTopologyAnalyzer.extract_interface_number(interface_name)

            intf_data = {
                'interface': interface_name,
                'base_interface': base_intf,
                'subif_numbers': subif_numbers,
                'ip': parsed['ip'],
                'prefix': parsed['prefix'],
                'network_cidr': parsed['network_cidr'],
                'is_physical': NetworkTopologyAnalyzer.is_physical_interface(interface_name),
                'is_mgmt': NetworkTopologyAnalyzer.is_mgmt_interface(interface_name, parsed['is_mgmt_network']),
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
                if (intf_data['is_loopback'] or
                        intf_data['is_mgmt'] or
                        (intf_data['is_physical'] and intf_data['is_p2p'])):
                    continue

            interfaces.append(intf_data)

        return interfaces

    @staticmethod
    def find_physical_links(devices_data: List[Dict[str, Any]]) -> List[List[Any]]:
        """Выявляет физические P2P связи через /31 и /30 сети с указанием вендора и типа."""
        # Маппинг имени → метаданные
        device_metadata: Dict[str, Dict[str, str]] = {
            device['device_name']: {
                'vendor': device['vendor'],
                'device_type': device['device_type']
            }
            for device in devices_data if device['device_name'] != 'unknown'
        }

        # Сбор физических интерфейсов
        device_interfaces: Dict[str, List[Dict[str, Any]]] = {}
        for device in devices_data:
            device_name = device['device_name']
            if device_name != 'unknown':
                device_interfaces[device_name] = NetworkTopologyAnalyzer.extract_device_interfaces(
                    device, filter_type='physical'
                )

        # Индексация сетей
        network_index: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
        for device_name, interfaces in device_interfaces.items():
            for intf in interfaces:
                net = intf['network_cidr']
                network_index.setdefault(net, []).append((device_name, intf))

        # Формирование связей
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

            dev1_meta = device_metadata.get(dev1_name, {'vendor': 'N/A', 'device_type': 'N/A'})
            dev2_meta = device_metadata.get(dev2_name, {'vendor': 'N/A', 'device_type': 'N/A'})

            links.append([
                dev1_name,
                dev1_meta['vendor'],
                dev1_meta['device_type'],
                intf1['interface'],
                intf1['ip'],
                dev2_name,
                dev2_meta['vendor'],
                dev2_meta['device_type'],
                intf2['interface'],
                intf2['ip'],
                network_cidr
            ])

        return links

    @staticmethod
    def find_mgmt_interfaces(devices_data: List[Dict[str, Any]]) -> List[List[str]]:
        """Извлекает управленческие интерфейсы."""
        mgmt_interfaces = []
        for device in devices_data:
            device_name = device['device_name']
            if device_name == 'unknown':
                continue
            mgmt_ifs = NetworkTopologyAnalyzer.extract_device_interfaces(device, filter_type='mgmt')
            for intf in mgmt_ifs:
                mgmt_interfaces.append([
                    device_name,
                    intf['interface'],
                    intf['ip'],
                    intf['network_cidr']
                ])

        mgmt_interfaces.sort(key=lambda x: (x[3], x[0]))
        return mgmt_interfaces

    @staticmethod
    def find_logical_links(devices_data: List[Dict[str, Any]]) -> List[List[str]]:
        """Выявляет логические связи (сервисные сети, VXLAN, логические P2P)."""
        logical_links = []
        processed_networks: Set[str] = set()
        processed_vni_pairs: Set[Tuple[str, str, int]] = set()

        # Сбор всех интерфейсов
        all_interfaces: Dict[str, List[Dict[str, Any]]] = {}
        for device in devices_data:
            device_name = device['device_name']
            if device_name != 'unknown':
                all_interfaces[device_name] = NetworkTopologyAnalyzer.extract_device_interfaces(
                    device, filter_type='all'
                )

        # 1. Сервисные сети (VBDIF/Vlanif)
        network_to_devices: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
        for device_name, interfaces in all_interfaces.items():
            for intf in interfaces:
                if (intf['interface'].startswith(('Vbdif', 'Vlanif')) and
                        24 <= intf['prefix'] <= 28 and
                        not intf['is_loopback']):
                    net = intf['network_cidr']
                    network_to_devices.setdefault(net, []).append((device_name, intf))

        for network_cidr, endpoints in network_to_devices.items():
            if len(endpoints) < 2 or network_cidr in processed_networks:
                continue
            processed_networks.add(network_cidr)
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

        # 2. VXLAN overlay (подынтерфейсы с номерами VNI)
        vni_map: Dict[int, List[Tuple[str, Dict[str, Any]]]] = {}
        for device_name, interfaces in all_interfaces.items():
            for intf in interfaces:
                if intf['subif_numbers'] and intf['base_interface'].startswith(('100GE', '40GE', '10GE')):
                    vni = intf['subif_numbers'][0]
                    if 1000 <= vni <= 16777215:
                        vni_map.setdefault(vni, []).append((device_name, intf))

        for vni, endpoints in vni_map.items():
            if len(endpoints) < 2:
                continue
            base_intf_groups: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
            for dev_name, intf in endpoints:
                base_intf_groups.setdefault(intf['base_interface'], []).append((dev_name, intf))
            for group_endpoints in base_intf_groups.values():
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

        # 3. Логические P2P через /30
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

    @staticmethod
    def analyze_topology(devices_data: List[Dict[str, Any]]) -> Dict[str, List[List[str]]]:
        """Полный анализ сетевой топологии."""
        return {
            "physical_links": NetworkTopologyAnalyzer.find_physical_links(devices_data),
            "mgmt_networks": NetworkTopologyAnalyzer.find_mgmt_interfaces(devices_data),
            "logical_links": NetworkTopologyAnalyzer.find_logical_links(devices_data)
        }


class ReportGenerator:
    """Генератор отчётов по результатам анализа."""

    @staticmethod
    def print_short_report(results: List[Dict[str, Any]]) -> None:
        """Печатает краткий отчёт в виде таблицы."""
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

        col_widths = [
            max(len(str(row[i])) for row in [headers] + rows)
            for i in range(len(headers))
        ]

        def format_row(row_data):
            return "   ".join(str(item).ljust(col_widths[i]) for i, item in enumerate(row_data))

        total_width = sum(col_widths) + 3 * (len(col_widths) - 1)
        print("\n" + "=" * total_width)
        print(format_row(headers))
        print("-" * total_width)
        for row in rows:
            print(format_row(row))
        print("=" * total_width + "\n")

    @staticmethod
    def print_topology_analysis(result: Dict[str, List[List[str]]]) -> None:
        """Печатает анализ топологии."""
        # Физические связи
        links = result.get("physical_links", [])
        print("\n" + "=" * 150)
        print("🔗 ФИЗИЧЕСКИЕ СВЯЗИ (Physical P2P Links)")
        print("=" * 150)
        if links:
            print(f"{'Устройство 1':<25} | {'Интерфейс':<18} | {'IP':<16} | "
                  f"{'Устройство 2':<25} | {'Интерфейс':<18} | {'IP':<16} | {'Сеть':<20}")
            print("-" * 150)
            for link in links:
                dev1, vendor1, type1, intf1, ip1, dev2, vendor2, type2, intf2, ip2, net = link
                print(f"{dev1:<25} | {intf1:<18} | {ip1:<16} | "
                      f"{dev2:<25} | {intf2:<18} | {ip2:<16} | {net:<20}")
            print(f"\n✅ Всего физических связей: {len(links)}")
        else:
            print("⚠️  Физические связи не обнаружены")

        # Управленческие сети
        mgmt = result.get("mgmt_networks", [])
        print("\n" + "=" * 100)
        print("🖥️  УПРАВЛЕНЧЕСКИЕ ИНТЕРФЕЙСЫ (Management Networks)")
        print("=" * 100)
        if mgmt:
            print(f"{'Устройство':<25} | {'Интерфейс':<18} | {'IP адрес':<16} | {'Сеть':<20}")
            print("-" * 100)
            for entry in mgmt:
                dev, intf, ip, net = entry
                print(f"{dev:<25} | {intf:<18} | {ip:<16} | {net:<20}")
            print(f"\n✅ Всего управленческих интерфейсов: {len(mgmt)}")

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
        print("🌐 ЛОГИЧЕСКИЕ СВЯЗИ (Logical Links: VXLAN Overlay, Service Networks)")
        print("=" * 130)
        if logical:
            print(f"{'Устройство 1':<25} | {'Интерфейс/IP':<25} | {'Устройство 2':<25} | "
                  f"{'Интерфейс/IP':<25} | {'Тип связи':<35}")
            print("-" * 130)
            for link in logical:
                dev1, intf_ip1, dev2, intf_ip2, desc = link
                print(f"{dev1:<25} | {intf_ip1:<25} | {dev2:<25} | {intf_ip2:<25} | {desc:<35}")
            print(f"\n✅ Всего логических связей: {len(logical)}")

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

    @staticmethod
    def write_detailed_report(results: List[Dict[str, Any]],
                              output_file: str,
                              links_result: Dict[str, List[List[str]]],
                              conf_dir: str) -> None:
        """Записывает подробный отчёт в файл."""
        from datetime import datetime

        with open(output_file, "w", encoding='utf-8') as f:
            f.write(f"Анализ сетевого оборудования - {len(results)} устройств\n")
            f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
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
                    with open(Path(conf_dir) / r['filename'], 'r', encoding='utf-8', errors='ignore') as config_file:
                        lines = config_file.readlines()
                        for line in lines[:10]:
                            f.write(f"  {line.rstrip()}\n")
                except Exception as e:
                    f.write(f"  ⚠️ Не удалось прочитать конфигурацию: {str(e)}\n")

                f.write("\n")

            links = links_result.get("physical_links", [])
            if not links:
                f.write("⚠️  Физические связи не обнаружены\n")
            else:
                f.write("### Таблица связей между устройствами\n")
                f.write("\n" + "=" * 150 + "\n")
                f.write(f"{'Устройство 1':<25} | {'Интерфейс':<18} | {'IP':<16} | "
                        f"{'Устройство 2':<25} | {'Интерфейс':<18} | {'IP':<16} | {'Сеть':<20}\n")
                f.write("=" * 150 + "\n")

                for link in links:
                    dev1, vendor1, type1, intf1, ip1, dev2, vendor2, type2, intf2, ip2, net = link
                    f.write(f"{dev1:<25} | {intf1:<18} | {ip1:<16} | "
                            f"{dev2:<25} | {intf2:<18} | {ip2:<16} | {net:<20}\n")

                f.write("=" * 150 + "\n")
                f.write(f"Всего обнаружено физических связей: {len(links)}\n")

            # Управленческие сети
            mgmt = links_result.get("mgmt_networks", [])
            f.write("\n" + "=" * 100 + "\n")
            f.write(" 🖥️  УПРАВЛЕНЧЕСКИЕ ИНТЕРФЕЙСЫ (Management Networks)\n")
            f.write("=" * 100 + "\n")
            if mgmt:
                f.write(f"{'Устройство':<25} | {'Интерфейс':<18} | {'IP адрес':<16} | {'Сеть':<20}\n")
                f.write("-" * 100 + "\n")
                for entry in mgmt:
                    dev, intf, ip, net = entry
                    f.write(f"{dev:<25} | {intf:<18} | {ip:<16} | {net:<20}\n")
                f.write(f"\n✅ Всего управленческих интерфейсов: {len(mgmt)}\n")

                networks = {}
                for entry in mgmt:
                    net = entry[3]
                    networks.setdefault(net, []).append(f"{entry[0]} ({entry[2]})")

                f.write("\nГруппировка по сетям управления:\n")
                for net, devices in sorted(networks.items()):
                    f.write(f"  • {net}: {', '.join(devices)}\n")
            else:
                f.write("⚠️  Управленческие интерфейсы не обнаружены\n")

            # Логические связи
            logical = links_result.get("logical_links", [])
            f.write("\n" + "=" * 130 + "\n")
            f.write(" 🌐 ЛОГИЧЕСКИЕ СВЯЗИ (Logical Links: VXLAN Overlay, Service Networks)\n")
            f.write("=" * 130 + "\n")
            if logical:
                f.write(f"{'Устройство 1':<25} | {'Интерфейс/IP':<25} | {'Устройство 2':<25} | "
                        f"{'Интерфейс/IP':<25} | {'Тип связи':<35}\n")
                f.write("-" * 130 + "\n")
                for link in logical:
                    dev1, intf_ip1, dev2, intf_ip2, desc = link
                    f.write(f"{dev1:<25} | {intf_ip1:<25} | {dev2:<25} | {intf_ip2:<25} | {desc:<35}\n")
                f.write(f"\n✅ Всего логических связей: {len(logical)}\n")

                vxlan_count = sum(1 for l in logical if 'VXLAN' in l[4])
                service_count = sum(1 for l in logical if 'Service Network' in l[4])
                p2p_count = sum(1 for l in logical if 'Logical P2P' in l[4])

                f.write("\nСтатистика логических связей:\n")
                if vxlan_count:
                    f.write(f"  • VXLAN Overlay (VNI): {vxlan_count}\n")
                if service_count:
                    f.write(f"  • Сервисные сети (L3): {service_count}\n")
                if p2p_count:
                    f.write(f"  • Логические P2P (/30): {p2p_count}\n")
            else:
                f.write("ℹ️  Логические связи не обнаружены (требуется дополнительная информация о конфигурации тоннелей)\n")

            f.write(f"\n✅ Детальная информация сохранена в файл: {output_file}\n")

        print(f"✅ Детальная информация сохранена в файл: \033[32m{output_file}\033[0m\n\n")