# Поддерживаемые вендоры и типы устройств

## Обзор

NetConf_Parser поддерживает автоматическое распознавание и визуализацию сетевого оборудования следующих вендоров:

---

## 📡 Коммутаторы (Switch)

### Cisco
- **Модели**: WS-C2960, WS-C2960S, WS-C2960+, C2960, C3750, C3650, C3850
- **Серия Catalyst 9000**: C9200, C9200L, C9300, C9300L, C9400, C9404R, C9500, C9600
- **Типы**: L2/L3 коммутаторы доступа и агрегации
- **Шаблон**: `switch`

### HPE/Aruba (Comware)
- **Серия 5510**: JH149A (24G SFP + 4SFP+ HI)
- **Серия 5130**: JG936A (24G PoE+), JG937A (48G PoE+)
- **Серия 5700/5900/5400R**: L3 коммутаторы
- **Особенности**: Поддержка IRF (Intelligent Resilient Framework)
- **Шаблон**: `switch`, `carrier_switch`

### Qtech
- **QSW-3310**: 12T-I-POE-DC (8 GE + 4 SFP), 28TX-POE-AC (24 GE + 4 10GE)
- **QSW-6910**: 26F (26 портов 10G SFP+, L3 Routing Switch)
- **Особенности**: Поддержка AggregatePort, OSPF
- **Шаблон**: `switch`

### D-Link
- **MES3300**: MES3300-4020 (10 GE, 8 PoE+)
- **MES3710P**: 12-портовый PoE+ коммутатор
- **NIS-3500**: 3226PGE, 3408PGE (OEM платформа)
- **Особенности**: Loopback detection, Spanning-tree portfast
- **Шаблон**: `switch`

### TFortis
- **NIS-3500**: 3226PGE, 3408PGE
- **PSW Series**: PSW-2G4F-UPS, PSW-4G2F-UPS
- **Особенности**: Ring V2 protection (ERPS), PoE приоритеты
- **Шаблон**: `switch`

### Arista
- **Серия EOS**: L2/L3 коммутаторы
- **Шаблон**: `switch`

### Dell
- **Серия N**: N1100, N2000, N3000, N4000
- **Шаблон**: `switch`

### MikroTik
- **Серия CRS**: Cloud Router Switch
- **Шаблон**: `switch`

---

## 🔥 Межсетевые экраны (Firewall)

### Cisco ASA
- **Модели**: ASA 5500-X серии
- **Шаблон**: `firewall`

### Fortinet FortiGate
- **Модели**: Все серии FortiGate
- **Шаблон**: `firewall`

### Palo Alto Networks
- **Модели**: PA-Series, VM-Series
- **Шаблон**: `firewall`

### Huawei
- **Серия USG**: USG6000, USG9500
- **Шаблон**: `firewall`

---

## 🌐 Маршрутизаторы (Router)

### Cisco
- **Серия ISR**: 1900, 2900, 3900, 4000
- **Серия ASR**: 1000, 5000, 9000
- **Шаблон**: `router`

### Juniper
- **Серия MX**: MX5, MX10, MX40, MX80, MX204
- **Серия PTX**: Packet Transport
- **Шаблон**: `router`

### MikroTik
- **Серия RB**: RB4011, RB5009, CCR серии
- **Шаблон**: `router`

### Huawei
- **Серия NE**: NE40E, NE80E, NE4000
- **Серия AR**: AR1200, AR2200, AR3200
- **Шаблон**: `carrier_router`, `enterprise_router`

### Qtech
- **QSW-6910**: L3 Routing Switch с OSPF
- **Шаблон**: `switch` (с функциями маршрутизации)

---

## 📶 Беспроводные контроллеры (Wireless Controller)

### Cisco
- **Серия 5500**: 5508, 5520
- **Серия 3500**: 3504
- **Встроенные**: на базе Catalyst
- **Шаблон**: `default`

### Aruba
- **Серия 7000**: 7010, 7024, 7030
- **Серия 9000**: 9004, 9008
- **Шаблон**: `wireless_controller`

### MikroTik
- **CAPsMAN**: Centralized AP Management
- **Шаблон**: `wireless_controller`

---

## ⚖️ Балансировщики нагрузки (Load Balancer)

### F5 BIG-IP
- **Серия 2000s**: 2250s, 2450s
- **Серия 4000s**: 4200s, 4480s
- **Серия 10000s**: 10200s, 10400s
- **Шаблон**: `default`

---

## 📡 Операторское оборудование (Carrier)

### Huawei
- **OLT устройства**: MA5600, MA5800 (GPON/EPON)
- **Carrier Switch**: CE6800, CE8800, CE12800 (Data Center)
- **Carrier Router**: NE40E, NE80E, NE4000
- **Шаблон**: `olt_device`, `carrier_switch`, `carrier_router`

### HPE/Aruba
- **Carrier Switch**: 5900 серии (Data Center)
- **Шаблон**: `carrier_switch`

---

## 🔗 Типы связей

### Физические связи (Physical Link)
- **Цвет**: Черный (#000000)
- **Стиль**: Сплошная линия, толщина 3px
- **Применение**: Физические соединения между устройствами

### Логические связи (Logical Link)
- **Цвет**: Синий (#1e88e5)
- **Стиль**: Пунктирная линия, толщина 2px
- **Применение**: VLAN, VXLAN, туннели

### Управленческие связи (Management Link)
- **Цвет**: Зеленый (#43a047)
- **Стиль**: Пунктирная линия, толщина 2px
- **Применение**: Out-of-band management, OOB сети

### Сети (Network)
- **Цвет**: Светло-серый (#c0cfe2)
- **Стиль**: Прямоугольник с закругленными углами
- **Применение**: L2/L3 сети, подсети

---

## 📊 Статистика поддержки

| Категория | Вендоров | Моделей | Шаблон |
|-----------|----------|---------|--------|
| Switch | 10 | 50+ | switch |
| Firewall | 4 | 20+ | firewall |
| Router | 5 | 30+ | router |
| Wireless | 3 | 15+ | default |
| Load Balancer | 1 | 10+ | default |
| Carrier | 2 | 20+ | carrier_* |
| **ВСЕГО** | **15** | **145+** | **6** |

---

## 🛠 Добавление нового вендора

Для добавления поддержки нового вендора:

1. Создайте файл шаблона в `patterns/devices/<vendor>.json`
2. Добавьте запись в `patterns/drawio/templates/index.yaml`
3. При необходимости создайте стиль в `patterns/drawio/templates/stencils.yaml`
4. Обновите этот файл с описанием

Пример структуры шаблона:
```json
{
  "vendor": "NewVendor",
  "version": "1.0",
  "vendor_signatures": ["сигнатура1", "сигнатура2"],
  "name_patterns": [...],
  "model_patterns": [...],
  "type_inference": [...],
  "network_extraction_rules": {...}
}
```

---

## 📅 Дата обновления

18 февраля 2025 г.

## 👤 Версия документа

Версия: 2.0 (с поддержкой 15 вендоров и 126+ устройств)
