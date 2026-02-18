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
        
        # Дополнительное извлечение всех IP интерфейсов для b4com
        self.all_ip_interfaces = self._extract_all_ip_interfaces()

        # Этап 5: Извлечение дополнительной информации (BGP, Port-Channel, VXLAN, Management)
        bgp_rules = pattern.get("bgp_extraction_rules", {})
        if bgp_rules.get("enabled"):
            self.bgp_info = self._extract_bgp_info(bgp_rules)
        else:
            self.bgp_info = {}
        
        pc_rules = pattern.get("port_channel_extraction_rules", {})
        if pc_rules.get("enabled"):
            self.port_channels = self._extract_port_channels(pc_rules)
        else:
            self.port_channels = []
        
        vxlan_rules = pattern.get("vxlan_extraction_rules", {})
        if vxlan_rules.get("enabled"):
            self.vxlan_info = self._extract_vxlan_info(vxlan_rules)
        else:
            self.vxlan_info = {}
        
        mgmt_rules = pattern.get("management_extraction_rules", {})
        if mgmt_rules.get("enabled"):
            self.management_info = self._extract_management_info(mgmt_rules)
        else:
            self.management_info = {}

        return True

    def _extract_bgp_info(self, rules: Dict) -> Dict[str, Any]:
        """Извлекает информацию о BGP конфигурации."""
        result = {
            "enabled": False,
            "asn": None,
            "router_id": None,
            "neighbors": [],
            "evpn_neighbors": [],
            "address_families": []
        }
        
        neighbor_descriptions = {}
        
        for line in self.content_lines:
            # ASN
            if rules.get("asn_pattern"):
                match = re.search(rules["asn_pattern"], line, re.IGNORECASE)
                if match:
                    result["enabled"] = True
                    result["asn"] = match.group(1)
            
            # Router ID
            if rules.get("router_id_pattern"):
                match = re.search(rules["router_id_pattern"], line, re.IGNORECASE)
                if match:
                    result["router_id"] = match.group(1)
            
            # Neighbor с remote-as
            if rules.get("neighbor_pattern"):
                match = re.search(rules["neighbor_pattern"], line, re.IGNORECASE)
                if match:
                    neighbor_ip = match.group(1)
                    neighbor_as = match.group(2)
                    # Проверяем, есть ли уже такой сосед
                    existing = next((n for n in result["neighbors"] if n["ip"] == neighbor_ip), None)
                    if existing:
                        existing["remote_as"] = neighbor_as
                    else:
                        result["neighbors"].append({
                            "ip": neighbor_ip,
                            "remote_as": neighbor_as,
                            "description": neighbor_descriptions.get(neighbor_ip, ""),
                            "evpn_enabled": False
                        })
            
            # Neighbor description
            if rules.get("neighbor_desc_pattern"):
                match = re.search(rules["neighbor_desc_pattern"], line, re.IGNORECASE)
                if match:
                    neighbor_ip = match.group(1)
                    description = match.group(2)
                    neighbor_descriptions[neighbor_ip] = description
                    # Обновляем существующего соседа
                    existing = next((n for n in result["neighbors"] if n["ip"] == neighbor_ip), None)
                    if existing:
                        existing["description"] = description
            
            # Address-family
            if rules.get("address_family_pattern"):
                match = re.search(rules["address_family_pattern"], line, re.IGNORECASE)
                if match:
                    af = f"{match.group(1)} {match.group(2)}"
                    if af not in result["address_families"]:
                        result["address_families"].append(af)
            
            # EVPN neighbor activate
            if rules.get("evpn_neighbors_pattern"):
                match = re.search(rules["evpn_neighbors_pattern"], line, re.IGNORECASE)
                if match:
                    neighbor_ip = match.group(1)
                    existing = next((n for n in result["neighbors"] if n["ip"] == neighbor_ip), None)
                    if existing:
                        existing["evpn_enabled"] = True
                    result["evpn_neighbors"].append(neighbor_ip)
        
        # Применяем описания ко всем соседям
        for neighbor in result["neighbors"]:
            if not neighbor["description"]:
                neighbor["description"] = neighbor_descriptions.get(neighbor["ip"], "")
        
        return result

    def _extract_port_channels(self, rules: Dict) -> List[Dict[str, Any]]:
        """Извлекает информацию о Port-Channel интерфейсах."""
        port_channels = []
        current_pc = None
        
        for line in self.content_lines:
            # Новый Port-Channel
            if rules.get("port_channel_pattern"):
                match = re.search(rules["port_channel_pattern"], line, re.IGNORECASE)
                if match:
                    if current_pc:
                        port_channels.append(current_pc)
                    current_pc = {
                        "name": match.group(1),
                        "description": "",
                        "members": [],
                        "mode": "",
                        "vlans": "",
                        "shutdown": False
                    }
                    continue
            
            if current_pc:
                # Description
                if rules.get("port_channel_desc_pattern"):
                    match = re.search(rules["port_channel_desc_pattern"], line, re.IGNORECASE)
                    if match:
                        current_pc["description"] = match.group(1).strip()
                
                # Channel-group members
                if rules.get("port_channel_members_pattern"):
                    match = re.search(rules["port_channel_members_pattern"], line, re.IGNORECASE)
                    if match:
                        current_pc["members"].append({
                            "group": match.group(1),
                            "mode": match.group(2)
                        })
                
                # VLANs
                if rules.get("port_channel_vlans_pattern"):
                    match = re.search(rules["port_channel_vlans_pattern"], line, re.IGNORECASE)
                    if match:
                        current_pc["vlans"] = match.group(1)
                
                # Shutdown status
                if re.search(r"^\s*shutdown\s*$", line, re.IGNORECASE):
                    current_pc["shutdown"] = True
        
        if current_pc:
            port_channels.append(current_pc)
        
        return port_channels

    def _extract_vxlan_info(self, rules: Dict) -> Dict[str, Any]:
        """Извлекает информацию о VXLAN конфигурации."""
        result = {
            "enabled": False,
            "vtep_ip": None,
            "vnis": [],
            "anycast_mac": None,
            "mac_vrfs": []
        }
        
        current_mac_vrf = None
        in_mac_vrf = False
        
        for line in self.content_lines:
            # VTEP IP
            if rules.get("vtep_ip_pattern"):
                match = re.search(rules["vtep_ip_pattern"], line, re.IGNORECASE)
                if match:
                    result["enabled"] = True
                    result["vtep_ip"] = match.group(1)
            
            # VNI
            if rules.get("vni_pattern"):
                match = re.search(rules["vni_pattern"], line, re.IGNORECASE)
                if match:
                    vni_id = match.group(1)
                    bridge_vlan = match.group(2)
                    result["vnis"].append({
                        "vni": vni_id,
                        "bridge_vlan": bridge_vlan,
                        "name": ""
                    })
            
            # VNI name
            if rules.get("vni_name_pattern"):
                match = re.search(rules["vni_name_pattern"], line, re.IGNORECASE)
                if match:
                    if result["vnis"]:
                        result["vnis"][-1]["name"] = match.group(1)
            
            # Anycast gateway MAC
            if rules.get("evpn_irb_mac_pattern"):
                match = re.search(rules["evpn_irb_mac_pattern"], line, re.IGNORECASE)
                if match:
                    result["anycast_mac"] = match.group(1)
            
            # MAC VRF start - проверяем начало секции
            if rules.get("mac_vrf_pattern"):
                match = re.search(rules["mac_vrf_pattern"], line, re.IGNORECASE)
                if match:
                    if current_mac_vrf:
                        result["mac_vrfs"].append(current_mac_vrf)
                    current_mac_vrf = {
                        "name": match.group(1),
                        "rd": "",
                        "route_target": "",
                        "description": ""
                    }
                    in_mac_vrf = True
                    continue
            
            if in_mac_vrf and current_mac_vrf:
                # RD
                if rules.get("mac_vrf_rd_pattern"):
                    match = re.search(rules["mac_vrf_rd_pattern"], line, re.IGNORECASE)
                    if match:
                        current_mac_vrf["rd"] = match.group(1)
                
                # Route-target
                if rules.get("mac_vrf_rt_pattern"):
                    match = re.search(rules["mac_vrf_rt_pattern"], line, re.IGNORECASE)
                    if match:
                        current_mac_vrf["route_target"] = match.group(1)
                
                # Description
                if rules.get("mac_vrf_desc_pattern"):
                    match = re.search(rules["mac_vrf_desc_pattern"], line, re.IGNORECASE)
                    if match:
                        current_mac_vrf["description"] = match.group(1)
                
                # Выход из секции MAC VRF - новая секция или конец
                if re.search(r"^mac vrf\s+\S+", line, re.IGNORECASE) and current_mac_vrf["name"] != line.split()[-1]:
                    pass  # Обработано выше
                elif re.search(r"^evpn irb-forwarding", line, re.IGNORECASE):
                    in_mac_vrf = False
        
        if current_mac_vrf:
            result["mac_vrfs"].append(current_mac_vrf)
        
        return result

    def _extract_management_info(self, rules: Dict) -> Dict[str, Any]:
        """Извлекает информацию об управлении."""
        result = {
            "mgmt_interface": None,
            "mgmt_ip": None,
            "mgmt_mask": None,
            "mgmt_vrf": None,
            "default_gateway": None,
            "default_gateway_iface": None
        }
        
        in_mgmt_interface = False
        
        for line in self.content_lines:
            # Management interface
            if rules.get("mgmt_interface_pattern"):
                match = re.search(rules["mgmt_interface_pattern"], line, re.IGNORECASE)
                if match:
                    result["mgmt_interface"] = match.group(1)
                    in_mgmt_interface = True
                    continue
            
            if in_mgmt_interface:
                # Management VRF
                if rules.get("mgmt_vrf_pattern"):
                    match = re.search(rules["mgmt_vrf_pattern"], line, re.IGNORECASE)
                    if match:
                        result["mgmt_vrf"] = match.group(1)
                
                # Management IP - CIDR формат (10.7.8.1/24) или с маской
                if rules.get("mgmt_ip_pattern"):
                    # CIDR формат
                    cidr_match = re.search(r"ip address\s+(\S+)/(\d+)", line, re.IGNORECASE)
                    if cidr_match:
                        result["mgmt_ip"] = cidr_match.group(1)
                        result["mgmt_mask"] = cidr_match.group(2)
                    else:
                        match = re.search(rules["mgmt_ip_pattern"], line, re.IGNORECASE)
                        if match:
                            result["mgmt_ip"] = match.group(1)
                            result["mgmt_mask"] = match.group(2)
                
                # Выход из секции интерфейса
                if re.search(r"^interface\s+", line, re.IGNORECASE) and not re.search(r"^interface\s+(eth0|mgmt)", line, re.IGNORECASE):
                    in_mgmt_interface = False
            
            # Default route
            if rules.get("default_route_pattern"):
                match = re.search(rules["default_route_pattern"], line, re.IGNORECASE)
                if match:
                    result["mgmt_vrf"] = match.group(1)
                    result["default_gateway"] = match.group(2)
                    # Пытаемся извлечь интерфейс из следующей строки или из gateway
                    gw_parts = result["default_gateway"].split()
                    if len(gw_parts) > 1:
                        result["default_gateway"] = gw_parts[0]
                        result["default_gateway_iface"] = gw_parts[1]
        
        return result

    def _extract_all_ip_interfaces(self) -> List[Dict[str, str]]:
        """Извлекает все интерфейсы с IP адресами из конфигурации."""
        interfaces = []
        current_interface = None
        is_shutdown = False
        
        for line in self.content_lines:
            # Проверка на интерфейс
            intf_match = re.search(r"^interface\s+(\S+)", line, re.IGNORECASE)
            if intf_match:
                # Сохраняем предыдущий интерфейс если был IP
                if current_interface and not is_shutdown and current_interface.get('ip'):
                    interfaces.append({
                        'interface': current_interface['name'],
                        'ip': current_interface.get('ip'),
                        'mask': current_interface.get('mask'),
                        'description': current_interface.get('description', '')
                    })
                
                current_interface = {
                    'name': intf_match.group(1),
                    'ip': None,
                    'mask': None,
                    'description': ''
                }
                is_shutdown = False
                continue
            
            if current_interface:
                # IP адрес в формате CIDR (10.7.0.0/31) или с маской (10.7.0.0 255.255.255.254)
                ip_cidr_match = re.search(r"ip address\s+(\S+)/(\d+)", line, re.IGNORECASE)
                if ip_cidr_match:
                    current_interface['ip'] = ip_cidr_match.group(1)
                    current_interface['mask'] = ip_cidr_match.group(2)  # CIDR префикс
                else:
                    ip_mask_match = re.search(r"ip address\s+(\S+)\s+(\S+)", line, re.IGNORECASE)
                    if ip_mask_match:
                        current_interface['ip'] = ip_mask_match.group(1)
                        current_interface['mask'] = ip_mask_match.group(2)
                
                # Description
                desc_match = re.search(r"description\s+(.+)", line, re.IGNORECASE)
                if desc_match:
                    current_interface['description'] = desc_match.group(1).strip()
                
                # Shutdown
                if re.search(r"^\s*shutdown\s*$", line, re.IGNORECASE):
                    is_shutdown = True
        
        # Последний интерфейс
        if current_interface and not is_shutdown and current_interface.get('ip'):
            interfaces.append({
                'interface': current_interface['name'],
                'ip': current_interface['ip'],
                'mask': current_interface['mask'],
                'description': current_interface.get('description', '')
            })
        
        return interfaces

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
            "all_vlans": self.all_vlans,
            "bgp_info": getattr(self, 'bgp_info', {}),
            "port_channels": getattr(self, 'port_channels', []),
            "vxlan_info": getattr(self, 'vxlan_info', {}),
            "management_info": getattr(self, 'management_info', {}),
            "all_ip_interfaces": getattr(self, 'all_ip_interfaces', [])
        }


class NetworkTopologyAnalyzer:
    """Анализатор сетевой топологии на основе данных об устройствах."""

    @staticmethod
    def netmask_to_prefix(netmask: str) -> int:
        """Преобразует маску из dotted-decimal в префикс."""
        try:
            # Обработка CIDR нотации (например, "31", "30")
            if netmask_str := netmask.strip():
                if netmask_str.isdigit():
                    return int(netmask_str)
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
        # Обработка формата "ip/mask" или "ip mask" или "ip/secondary"
        parts = network_entry.replace('secondary', '').strip().split()
        if len(parts) >= 1:
            network_str = parts[0]
            if '/' in network_str:
                ip_str, netmask_str = network_str.split('/', 1)
            else:
                ip_str = network_str
                netmask_str = '32'  # Default to host route
            
            # Обработка CIDR нотации
            if netmask_str.isdigit():
                prefix = int(netmask_str)
            else:
                try:
                    prefix = NetworkTopologyAnalyzer.netmask_to_prefix(netmask_str)
                except ValueError:
                    prefix = 32
            
            # Вычисляем реальный адрес сети (network address)
            try:
                network = ipaddress.IPv4Network(f'{ip_str}/{prefix}', strict=False)
                network_cidr = str(network)
            except ValueError:
                network_cidr = f"{ip_str}/{prefix}"
            
            return {
                'ip': ip_str,
                'prefix': prefix,
                'network_cidr': network_cidr,
                'is_loopback': prefix == 32,
                'is_mgmt_network': prefix in (24, 23, 22),
                'is_p2p': prefix in (31, 30)
            }
        
        return {
            'ip': network_entry,
            'prefix': 32,
            'network_cidr': f"{network_entry}/32",
            'is_loopback': False,
            'is_mgmt_network': False,
            'is_p2p': False
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
        device_name = device.get('device_name', 'unknown')
        processed_networks = set()
        
        # 1. Все IP интерфейсы из all_ip_interfaces (для b4com)
        for intf_entry in device.get('all_ip_interfaces', []):
            interface_name = intf_entry.get('interface', '')
            ip = intf_entry.get('ip')
            mask = intf_entry.get('mask', '32')
            description = intf_entry.get('description', '')
            
            if interface_name and ip:
                # Преобразуем маску
                if mask.isdigit():
                    prefix = int(mask)
                else:
                    try:
                        prefix = NetworkTopologyAnalyzer.netmask_to_prefix(mask)
                    except ValueError:
                        prefix = 32
                
                # Вычисляем реальный адрес сети
                try:
                    network = ipaddress.IPv4Network(f'{ip}/{prefix}', strict=False)
                    network_cidr = str(network)
                except ValueError:
                    network_cidr = f"{ip}/{prefix}"

                # Пропускаем дубликаты и loopback
                if network_cidr in processed_networks:
                    continue
                processed_networks.add(network_cidr)
                
                base_intf, subif_numbers = NetworkTopologyAnalyzer.extract_interface_number(interface_name)
                
                intf_data = {
                    'interface': interface_name,
                    'base_interface': base_intf,
                    'subif_numbers': subif_numbers,
                    'ip': ip,
                    'prefix': prefix,
                    'network_cidr': network_cidr,
                    'description': description,
                    'is_physical': NetworkTopologyAnalyzer.is_physical_interface(interface_name),
                    'is_mgmt': NetworkTopologyAnalyzer.is_mgmt_interface(interface_name, prefix in (24, 23, 22)),
                    'is_loopback': interface_name.lower().startswith('lo'),
                    'is_p2p': prefix in (31, 30),
                    'source': 'all_ip'
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
        
        # 2. Management interface из management_info (если ещё не добавлен)
        if filter_type in ('all', 'mgmt'):
            mgmt_info = device.get('management_info', {})
            if mgmt_info.get('mgmt_interface') and mgmt_info.get('mgmt_ip'):
                mgmt_ip = mgmt_info['mgmt_ip']
                mgmt_mask = mgmt_info.get('mgmt_mask', '24')
                mgmt_intf = mgmt_info['mgmt_interface']
                
                # Проверяем, не добавлен ли уже
                already_added = any(
                    intf['interface'] == mgmt_intf and intf['ip'] == mgmt_ip 
                    for intf in interfaces
                )
                
                if not already_added:
                    # Преобразуем маску если нужно
                    if mgmt_mask.isdigit():
                        prefix = int(mgmt_mask)
                    else:
                        try:
                            prefix = NetworkTopologyAnalyzer.netmask_to_prefix(mgmt_mask)
                        except ValueError:
                            prefix = 24
                    
                    interfaces.append({
                        'interface': mgmt_intf,
                        'base_interface': mgmt_intf,
                        'subif_numbers': [],
                        'ip': mgmt_ip,
                        'prefix': prefix,
                        'network_cidr': f"{mgmt_ip}/{prefix}",
                        'is_physical': True,
                        'is_mgmt': True,
                        'is_loopback': False,
                        'is_p2p': False,
                        'source': 'management'
                    })
        
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
                    device.get('vendor', 'unknown'),  # Add vendor
                    device.get('device_type', 'unknown'),  # Add type
                    intf['interface'],
                    intf['ip'],
                    intf['network_cidr']
                ])

        mgmt_interfaces.sort(key=lambda x: (x[5], x[0]))  # Sort by network_cidr then device_name
        return mgmt_interfaces

    @staticmethod
    def find_logical_links(devices_data: List[Dict[str, Any]]) -> List[List[str]]:
        """Выявляет логические связи (сервисные сети, VXLAN, логические P2P)."""
        logical_links = []
        processed_networks: Set[str] = set()
        processed_vni_pairs: Set[Tuple[str, str, int]] = set()

        # Создание маппинга имени устройства к его вендору и типу
        device_metadata: Dict[str, Dict[str, str]] = {
            device['device_name']: {
                'vendor': device['vendor'],
                'device_type': device['device_type']
            }
            for device in devices_data
            if device['device_name'] != 'unknown'
        }

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

                    # Получаем метаданные устройств
                    dev1_meta = device_metadata.get(dev1_name, {'vendor': 'N/A', 'device_type': 'N/A'})
                    dev2_meta = device_metadata.get(dev2_name, {'vendor': 'N/A', 'device_type': 'N/A'})

                    logical_links.append([
                        dev1_name,
                        dev1_meta['vendor'],
                        dev1_meta['device_type'],
                        f"{intf1['interface']}/{intf1['ip']}",
                        dev2_name,
                        dev2_meta['vendor'],
                        dev2_meta['device_type'],
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
                        # Получаем метаданные устройств
                        dev1_meta = device_metadata.get(dev1_name, {'vendor': 'N/A', 'device_type': 'N/A'})
                        dev2_meta = device_metadata.get(dev2_name, {'vendor': 'N/A', 'device_type': 'N/A'})

                        logical_links.append([
                            dev1_name,
                            dev1_meta['vendor'],
                            dev1_meta['device_type'],
                            f"{intf1['interface']}/{intf1['ip']}",
                            dev2_name,
                            dev2_meta['vendor'],
                            dev2_meta['device_type'],
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
            # Получаем метаданные устройств
            dev1_meta = device_metadata.get(dev1_name, {'vendor': 'N/A', 'device_type': 'N/A'})
            dev2_meta = device_metadata.get(dev2_name, {'vendor': 'N/A', 'device_type': 'N/A'})

            logical_links.append([
                dev1_name,
                dev1_meta['vendor'],
                dev1_meta['device_type'],
                f"{intf1['interface']}/{intf1['ip']}",
                dev2_name,
                dev2_meta['vendor'],
                dev2_meta['device_type'],
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
        print("\n" + "=" * 110)
        print("🖥️  УПРАВЛЕНЧЕСКИЕ ИНТЕРФЕЙСЫ (Management Networks)")
        print("=" * 110)
        if mgmt:
            print(f"{'Устройство':<25} |  {'Интерфейс':<18} | {'IP адрес':<16} | {'Сеть':<20}")
            print("-" * 110)
            for entry in mgmt:
                if len(entry) >= 6:
                    dev, vendor, dev_type, intf, ip, net = entry
                    print(f"{dev:<25} |  {intf:<18} | {ip:<16} | {net:<20}")
                else:
                    # Fallback for backward compatibility
                    dev, intf, ip, net = entry
                    print(f"{dev:<25} |  {intf:<18} | {ip:<16} | {net:<20}")
            print(f"\n✅ Всего управленческих интерфейсов: {len(mgmt)}")

            networks = {}
            for entry in mgmt:
                if len(entry) >= 6:
                    net = entry[5]
                    networks.setdefault(net, []).append(f"{entry[0]} ({entry[4]})")
                else:
                    net = entry[3]
                    networks.setdefault(net, []).append(f"{entry[0]} ({entry[2]})")

            print("\nГруппировка по сетям управления:")
            for net, devices in sorted(networks.items()):
                print(f"  • {net}: {', '.join(devices)}")
        else:
            print("⚠️  Управленческие интерфейсы не обнаружены")

        # Логические связи
        logical = result.get("logical_links", [])
        print("\n" + "=" * 160)
        print("🌐 ЛОГИЧЕСКИЕ СВЯЗИ (Logical Links: VXLAN Overlay, Service Networks)")
        print("=" * 160)
        if logical:
            print(f"{'Устройство 1':<25} | {'Интерфейс/IP':<25}    | {'Устройство 2':<25} | {'Интерфейс/IP':<25}    | {'Тип связи':<35}")
            print("-" * 160)
            for link in logical:
                if len(link) >= 9:
                    dev1, vendor1, type1, intf_ip1, dev2, vendor2, type2, intf_ip2, desc = link
                    print(f"{dev1:<25} |  {intf_ip1:<25} | {dev2:<25} |  {intf_ip2:<25} | {desc:<35}")
                else:
                    # Fallback for backward compatibility
                    dev1, intf_ip1, dev2, intf_ip2, desc = link
                    print(f"{dev1:<25} |  {intf_ip1:<25} | {dev2:<25} |  {intf_ip2:<25} | {desc:<35}")
            print(f"\n✅ Всего логических связей: {len(logical)}")

            # Calculate statistics considering the new structure
            vxlan_count = 0
            service_count = 0
            p2p_count = 0
            for l in logical:
                if len(l) >= 9:
                    desc = l[8]  # Description is at index 8 in new structure
                else:
                    desc = l[4]  # Description is at index 4 in old structure
                if 'VXLAN' in desc:
                    vxlan_count += 1
                if 'Service Network' in desc:
                    service_count += 1
                if 'Logical P2P' in desc:
                    p2p_count += 1

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
            f.write("\n" + "=" * 130 + "\n")
            f.write(" 🖥️  УПРАВЛЕНЧЕСКИЕ ИНТЕРФЕЙСЫ (Management Networks)\n")
            f.write("=" * 130 + "\n")
            if mgmt:
                f.write(f"{'Устройство':<25} | {'Вендор':<15} | {'Тип':<15} | {'Интерфейс':<18} | {'IP адрес':<16} | {'Сеть':<20}\n")
                f.write("-" * 130 + "\n")
                for entry in mgmt:
                    if len(entry) >= 6:
                        dev, vendor, dev_type, intf, ip, net = entry
                        f.write(f"{dev:<25} | {vendor:<15} | {dev_type:<15} | {intf:<18} | {ip:<16} | {net:<20}\n")
                    else:
                        # Fallback for backward compatibility
                        dev, intf, ip, net = entry
                        f.write(f"{dev:<25} | {'':<15} | {'':<15} | {intf:<18} | {ip:<16} | {net:<20}\n")
                f.write(f"\n✅ Всего управленческих интерфейсов: {len(mgmt)}\n")

                networks = {}
                for entry in mgmt:
                    if len(entry) >= 6:
                        net = entry[5]
                        networks.setdefault(net, []).append(f"{entry[0]} ({entry[4]})")
                    else:
                        net = entry[3]
                        networks.setdefault(net, []).append(f"{entry[0]} ({entry[2]})")

                f.write("\nГруппировка по сетям управления:\n")
                for net, devices in sorted(networks.items()):
                    f.write(f"  • {net}: {', '.join(devices)}\n")
            else:
                f.write("⚠️  Управленческие интерфейсы не обнаружены\n")

            # Логические связи
            logical = links_result.get("logical_links", [])
            f.write("\n" + "=" * 160 + "\n")
            f.write(" 🌐 ЛОГИЧЕСКИЕ СВЯЗИ (Logical Links: VXLAN Overlay, Service Networks)\n")
            f.write("=" * 160 + "\n")
            if logical:
                f.write(f"{'Устройство 1':<25} | {'Вендор':<12} | {'Тип':<15} | {'Интерфейс/IP':<25} | {'Устройство 2':<25} | {'Вендор':<12} | {'Тип':<15} | {'Интерфейс/IP':<25} | {'Тип связи':<35}\n")
                f.write("-" * 160 + "\n")
                for link in logical:
                    if len(link) >= 9:
                        dev1, vendor1, type1, intf_ip1, dev2, vendor2, type2, intf_ip2, desc = link
                        f.write(f"{dev1:<25} | {vendor1:<12} | {type1:<15} | {intf_ip1:<25} | {dev2:<25} | {vendor2:<12} | {type2:<15} | {intf_ip2:<25} | {desc:<35}\n")
                    else:
                        # Fallback for backward compatibility
                        dev1, intf_ip1, dev2, intf_ip2, desc = link
                        f.write(f"{dev1:<25} | {'':<12} | {'':<15} | {intf_ip1:<25} | {dev2:<25} | {'':<12} | {'':<15} | {intf_ip2:<25} | {desc:<35}\n")
                f.write(f"\n✅ Всего логических связей: {len(logical)}\n")

                # Calculate statistics considering the new structure
                vxlan_count = 0
                service_count = 0
                p2p_count = 0
                for l in logical:
                    if len(l) >= 9:
                        desc = l[8]  # Description is at index 8 in new structure
                    else:
                        desc = l[4]  # Description is at index 4 in old structure
                    if 'VXLAN' in desc:
                        vxlan_count += 1
                    if 'Service Network' in desc:
                        service_count += 1
                    if 'Logical P2P' in desc:
                        p2p_count += 1

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

    @staticmethod
    def draw_topology_ascii(results: List[Dict[str, Any]], 
                            links_result: Dict[str, List[List[str]]],
                            output_file: str) -> None:
        """Генерирует текстовую ASCII-диаграмму топологии и расширенную информацию."""
        from datetime import datetime

        with open(output_file, "a", encoding='utf-8') as f:
            # Заголовок секции топологии
            f.write("\n" + "=" * 130 + "\n")
            f.write(" 📊 ТЕКСТОВАЯ КАРТА ТОПОЛОГИИ СЕТИ\n")
            f.write("=" * 130 + "\n\n")

            # === СПИСЕК УСТРОЙСТВ ПО РОЛЯМ ===
            f.write("┌" + "─" * 128 + "┐\n")
            f.write("│" + " СПИСОК УСТРОЙСТВ ПО РОЛЯМ ".center(128) + "│\n")
            f.write("└" + "─" * 128 + "┘\n\n")

            spine_devices = [r for r in results if 'spn' in r['device_name'].lower()]
            leaf_devices = [r for r in results if 'lf' in r['device_name'].lower() and 'brl' not in r['device_name'].lower()]
            border_devices = [r for r in results if 'brl' in r['device_name'].lower()]

            f.write("  Spine (Ядро):\n")
            for dev in spine_devices:
                vxlan_ip = dev.get('vxlan_info', {}).get('vtep_ip', 'N/A')
                bgp_asn = dev.get('bgp_info', {}).get('asn', 'N/A')
                f.write(f"    ├── {dev['device_name']:<25} VTEP: {vxlan_ip:<15} ASN: {bgp_asn}\n")
            f.write("\n")

            f.write("  Leaf (Доступ):\n")
            for dev in leaf_devices:
                vxlan_ip = dev.get('vxlan_info', {}).get('vtep_ip', 'N/A')
                bgp_asn = dev.get('bgp_info', {}).get('asn', 'N/A')
                vlan_count = dev.get('total_vlans', 0)
                f.write(f"    ├── {dev['device_name']:<25} VTEP: {vxlan_ip:<15} ASN: {bgp_asn}  VLANs: {vlan_count}\n")
            f.write("\n")

            f.write("  Border Leaf (Граница):\n")
            for dev in border_devices:
                vxlan_ip = dev.get('vxlan_info', {}).get('vtep_ip', 'N/A')
                bgp_asn = dev.get('bgp_info', {}).get('asn', 'N/A')
                vlan_count = dev.get('total_vlans', 0)
                f.write(f"    ├── {dev['device_name']:<25} VTEP: {vxlan_ip:<15} ASN: {bgp_asn}  VLANs: {vlan_count}\n")
            f.write("\n")

            # === BGP ТОПОЛОГИЯ ===
            f.write("┌" + "─" * 128 + "┐\n")
            f.write("│" + " BGP ТОПОЛОГИЯ (EVPN) ".center(128) + "│\n")
            f.write("└" + "─" * 128 + "┘\n\n")

            # ASCII схема BGP
            f.write("                          ASN 65100 (Spine)\n")
            f.write("              ┌────────────┬────────────┬────────────┐\n")
            for dev in spine_devices:
                bgp_info = dev.get('bgp_info', {})
                router_id = bgp_info.get('router_id', 'N/A')
                f.write(f"          {dev['device_name']:<18} (RID: {router_id})\n")
            f.write("              │            │            │\n")
            f.write("     ─────────┴────────────┴────────────┴─────────\n")
            f.write("     │              │                  │         │\n")
            
            for dev in leaf_devices:
                bgp_info = dev.get('bgp_info', {})
                asn = bgp_info.get('asn', 'N/A')
                f.write(f"  ASN {asn:<5}         ASN {asn:<5}\n")
                f.write(f"  {dev['device_name']:<18}\n")
            
            for dev in border_devices:
                bgp_info = dev.get('bgp_info', {})
                asn = bgp_info.get('asn', 'N/A')
                f.write(f"          ASN {asn:<5}         ASN {asn:<5}\n")
                f.write(f"          {dev['device_name']:<18}\n")
            f.write("\n")

            # Детали BGP сессий
            f.write("  BGP Соседи:\n")
            for dev in results:
                bgp_info = dev.get('bgp_info', {})
                if bgp_info.get('enabled'):
                    f.write(f"\n    {dev['device_name']} (ASN {bgp_info.get('asn', 'N/A')}):\n")
                    neighbors = bgp_info.get('neighbors', [])[:5]  # Первые 5 соседей
                    for n in neighbors:
                        evpn_status = "✓ EVPN" if n.get('evpn_enabled') else ""
                        f.write(f"      ├── {n['ip']:<15} → AS {n['remote_as']:<6} {n.get('description', ''):<20} {evpn_status}\n")
                    if len(bgp_info.get('neighbors', [])) > 5:
                        f.write(f"      ... и ещё {len(bgp_info.get('neighbors', [])) - 5} соседей\n")
            f.write("\n")

            # === VXLAN ИНФОРМАЦИЯ ===
            f.write("┌" + "─" * 128 + "┐\n")
            f.write("│" + " VXLAN / EVPN КОНФИГУРАЦИЯ ".center(128) + "│\n")
            f.write("└" + "─" * 128 + "┘\n\n")

            f.write("  VTEP IP адреса:\n")
            for dev in results:
                vxlan_info = dev.get('vxlan_info', {})
                if vxlan_info.get('enabled'):
                    f.write(f"    ├── {dev['device_name']:<25} → {vxlan_info.get('vtep_ip', 'N/A')}\n")
            f.write("\n")

            anycast_mac = None
            for dev in results:
                vxlan_info = dev.get('vxlan_info', {})
                if vxlan_info.get('anycast_mac'):
                    anycast_mac = vxlan_info['anycast_mac']
                    break
            if anycast_mac:
                f.write(f"  Anycast Gateway MAC: {anycast_mac}\n\n")

            # VNI список (первое устройство с VNI)
            for dev in results:
                vxlan_info = dev.get('vxlan_info', {})
                vnis = vxlan_info.get('vnis', [])
                if vnis:
                    f.write("  VNI (VXLAN Network Identifier):\n")
                    f.write("    ┌" + "─" * 50 + "┬" + "─" * 15 + "┬" + "─" * 15 + "┐\n")
                    f.write("    │ " + "VNI".center(50) + " │ " + "Bridge VLAN".center(15) + " │ " + "VNI Name".center(15) + " │\n")
                    f.write("    ├" + "─" * 50 + "┼" + "─" * 15 + "┼" + "─" * 15 + "┤\n")
                    for vni in vnis[:10]:  # Первые 10 VNI
                        f.write(f"    │ {vni.get('vni', 'N/A'):<50} │ {vni.get('bridge_vlan', 'N/A'):<15} │ {vni.get('name', 'N/A'):<15} │\n")
                    if len(vnis) > 10:
                        f.write(f"    │ ... и ещё {len(vnis) - 10} VNI {' ' * 47}│\n")
                    f.write("    └" + "─" * 50 + "┴" + "─" * 15 + "┴" + "─" * 15 + "┘\n")
                    break
            f.write("\n")

            # MAC VRF (EVPN Route Targets) - пример с первого устройства
            mac_vrf_sample_device = None
            mac_vrf_sample_list = []
            for dev in results:
                vxlan_info = dev.get('vxlan_info', {})
                mac_vrfs = vxlan_info.get('mac_vrfs', [])
                if mac_vrfs:
                    mac_vrf_sample_device = dev['device_name']
                    mac_vrf_sample_list = mac_vrfs[:10]  # Берём первые 10 для примера
                    break
            
            if mac_vrf_sample_list:
                f.write(f"  MAC VRF (EVPN Route Targets) - пример с устройства {mac_vrf_sample_device}:\n")
                f.write("    ┌" + "─" * 30 + "┬" + "─" * 20 + "┬" + "─" * 20 + "┬" + "─" * 20 + "┐\n")
                f.write("    │ " + "VRF Name".center(30) + " │ " + "RD".center(20) + " │ " + "Route Target".center(20) + " │ " + "Description".center(20) + " │\n")
                f.write("    ├" + "─" * 30 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┤\n")
                for vrf in mac_vrf_sample_list:
                    name = vrf.get('name', 'N/A')[:28]
                    rd = vrf.get('rd', 'N/A')[:18]
                    rt = vrf.get('route_target', 'N/A')[:18]
                    desc = vrf.get('description', 'N/A')[:18]
                    f.write(f"    │ {name:<30} │ {rd:<20} │ {rt:<20} │ {desc:<20} │\n")
                total_mac_vrfs = sum(len(d.get('vxlan_info', {}).get('mac_vrfs', [])) for d in results)
                if total_mac_vrfs > len(mac_vrf_sample_list):
                    f.write(f"    │ ... и ещё {total_mac_vrfs - len(mac_vrf_sample_list)} MAC VRF\n")
                f.write("    └" + "─" * 30 + "┴" + "─" * 20 + "┴" + "─" * 20 + "┴" + "─" * 20 + "┘\n")
            f.write("\n")

            # === PORT-CHANNEL (LACP) ===
            f.write("┌" + "─" * 128 + "┐\n")
            f.write("│" + " PORT-CHANNEL (LACP) ".center(128) + "│\n")
            f.write("└" + "─" * 128 + "┘\n\n")

            for dev in results:
                port_channels = dev.get('port_channels', [])
                if port_channels:
                    f.write(f"  {dev['device_name']}:\n")
                    for pc in port_channels:
                        status = "▼ DOWN" if pc.get('shutdown') else "▲ UP"
                        members = ", ".join([f"grp{m['group']}({m['mode']})" for m in pc.get('members', [])])
                        f.write(f"    ├── {pc['name']:<10} {pc.get('description', ''):<35} VLANs: {pc.get('vlans', 'N/A'):<20} {status}\n")
                        if members:
                            f.write(f"    │            Members: {members}\n")
            f.write("\n")

            # === СЕТЬ УПРАВЛЕНИЯ ===
            f.write("┌" + "─" * 128 + "┐\n")
            f.write("│" + " СЕТЬ УПРАВЛЕНИЯ (Management OOB) ".center(128) + "│\n")
            f.write("└" + "─" * 128 + "┘\n\n")

            mgmt_network = None
            for dev in results:
                mgmt_info = dev.get('management_info', {})
                if mgmt_info.get('mgmt_ip'):
                    if not mgmt_network:
                        mgmt_network = f"10.7.8.0/{mgmt_info.get('mgmt_mask', '24')}"
                    f.write(f"    ├── {dev['device_name']:<25} → {mgmt_info.get('mgmt_interface', 'eth0')}: "
                           f"{mgmt_info.get('mgmt_ip')}/{mgmt_info.get('mgmt_mask', '24')} "
                           f"(GW: {mgmt_info.get('default_gateway', 'N/A')})\n")
            if mgmt_network:
                f.write(f"\n  Management Network: {mgmt_network}\n")
            f.write("\n")

            # === ASCII СХЕМА ТОПОЛОГИИ ===
            f.write("┌" + "─" * 128 + "┐\n")
            f.write("│" + " ФИЗИЧЕСКАЯ ТОПОЛОГИЯ (CLOS Architecture) ".center(128) + "│\n")
            f.write("└" + "─" * 128 + "┘\n\n")

            # Рисуем схему CLOS
            f.write("                              ╔════════════════════════════════════════╗\n")
            f.write("                              ║         SPINE LAYER (ASN 65100)        ║\n")
            f.write("                              ╚════════════════════════════════════════╝\n")
            f.write("                                       │        │        │\n")
            
            # Spine устройства
            spine_names = [d['device_name'] for d in spine_devices]
            f.write(f"                              {'  '.join([f'{s:<15}' for s in spine_names])}\n")
            f.write(f"                              {'  '.join(['│' * len(spine_names)])}\n")
            
            # Листья
            f.write("\n")
            f.write("    ╔════════════════════════════════════════════════════════════════════════════╗\n")
            f.write("    ║                    LEAF LAYER (Доступ/Граница)                             ║\n")
            f.write("    ╚════════════════════════════════════════════════════════════════════════════╝\n")
            
            all_leaf = leaf_devices + border_devices
            for dev in all_leaf:
                bgp_info = dev.get('bgp_info', {})
                vxlan_info = dev.get('vxlan_info', {})
                f.write(f"\n      {dev['device_name']:<20} ASN:{bgp_info.get('asn', 'N/A'):<6} VTEP:{vxlan_info.get('vtep_ip', 'N/A'):<15}\n")
                f.write(f"         │\\\n         ├─────────── подключено ко всем Spine (ECMP)\n         │/\n")
            
            f.write("\n")
            f.write("  Условные обозначения:\n")
            f.write("    ├── VTEP: VXLAN Tunnel End Point IP\n")
            f.write("    ├── ASN:  BGP Autonomous System Number\n")
            f.write("    ├── ECMP: Equal-Cost Multi-Path routing\n")
            f.write("    └── EVPN: Ethernet VPN (BGP control plane)\n")
            f.write("\n")

            # Итоговая статистика
            f.write("┌" + "─" * 128 + "┐\n")
            f.write("│" + " ИТОГОВАЯ СТАТИСТИКА ".center(128) + "│\n")
            f.write("└" + "─" * 128 + "┘\n\n")

            total_devices = len(results)
            total_spine = len(spine_devices)
            total_leaf = len(leaf_devices)
            total_border = len(border_devices)
            total_vlans = sum(r.get('total_vlans', 0) for r in results)
            total_vnis = sum(len(r.get('vxlan_info', {}).get('vnis', [])) for r in results)
            total_port_channels = sum(len(r.get('port_channels', [])) for r in results)
            total_bgp_sessions = sum(len(r.get('bgp_info', {}).get('neighbors', [])) for r in results)

            f.write(f"    Общее количество устройств:     {total_devices}\n")
            f.write(f"      ├── Spine:                    {total_spine}\n")
            f.write(f"      ├── Leaf:                     {total_leaf}\n")
            f.write(f"      └── Border Leaf:              {total_border}\n")
            f.write(f"\n")
            f.write(f"    VLAN (всего):                   {total_vlans}\n")
            f.write(f"    VXLAN VNI (всего):              {total_vnis}\n")
            f.write(f"    Port-Channel интерфейсов:       {total_port_channels}\n")
            f.write(f"    BGP сессий (всего):             {total_bgp_sessions}\n")
            f.write(f"\n")

            # Физические связи из links_result
            physical_links = links_result.get("physical_links", [])
            if physical_links:
                f.write(f"    Физических связей (P2P /31):    {len(physical_links)}\n")
            
            mgmt_networks = links_result.get("mgmt_networks", [])
            if mgmt_networks:
                f.write(f"    Управленческих интерфейсов:   {len(mgmt_networks)}\n")
            
            logical_links = links_result.get("logical_links", [])
            if logical_links:
                f.write(f"    Логических связей (Overlay):  {len(logical_links)}\n")
            
            f.write("\n" + "=" * 130 + "\n")
            f.write(f" Дата генерации отчёта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 130 + "\n")