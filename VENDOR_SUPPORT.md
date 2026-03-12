# Поддержка вендоров — NetConf Parser

## 📋 Обзор

NetConf Parser поддерживает автоматическое определение и анализ конфигураций сетевого оборудования от **16 вендоров** с извлечением полной информации о топологии сети.

---

## 🌐 Таблица поддержки вендоров

| Вендор | Файл шаблона | Версия | Статус | LLDP | Статус портов | BGP | OSPF | VRF | VXLAN/EVPN | Port-Channel |
|--------|-------------|--------|--------|------|---------------|-----|------|-----|------------|--------------|
| **B4COM** | b4com.json | 1.3 | ✅ Полный | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Cisco** | cisco.json | 2.1 | ✅ Полный | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ |
| **Huawei** | huawei.json | 1.3 | ✅ Полный | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| **Juniper** | juniper.json | 1.2 | ✅ Полный | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| **MikroTik** | mikrotik.json | 2.2 | ✅ Полный | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ⚠️ |
| **Arista** | arista.json | 1.2 | ✅ Базовый | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ⚠️ | ⚠️ |
| **HPE/Aruba (Comware)** | hpe_aruba.json | 2.1 | ✅ Полный | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ✅ |
| **F5 BIG-IP** | f5.json | 1.2 | ✅ Базовый | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Fortinet** | fortinet.json | 1.1 | ✅ Базовый | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Palo Alto** | paloalto.json | 1.1 | ✅ Базовый | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Dell** | dell.json | 1.1 | ✅ Базовый | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ⚠️ |
| **Aruba** | aruba.json | 1.1 | ✅ Базовый | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ⚠️ |
| **Qtech** | qtech.json | 1.0 | ✅ Базовый | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **D-Link** | dlink.json | 1.0 | ✅ Базовый | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **TFortis** | tfortis.json | 1.0 | ✅ Базовый | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Unknown (OEM)** | unknown.json | 1.0 | ✅ Базовый | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Условные обозначения:**
- ✅ **Полный** — полная поддержка всех функций
- ✅ **Базовый** — базовая поддержка (устройства, VLAN, интерфейсы)
- ⚠️ **Частично** — функция поддерживается частично
- ❌ **Нет** — функция не поддерживается

---

## 🔍 Детальная поддержка по вендорам

### 🥇 **Уровень 1: Полная поддержка**

#### **B4COM** (версия шаблона: 1.3)
**Платформы:**
- BCOM_S4148Q8U-BCOM-OS-DC-IPBASE (Data Center Switch)
- BCOM_S4132U-BCOM-OS-DC-IPBASE (Spine Switch)
- BCOM-MR350-BCOM-OS-SP-MR (Border Router)

**Извлекаемая информация:**
- ✅ Устройства: имя, модель, тип, вендор
- ✅ Физические связи: P2P линки /31, /30
- ✅ VLAN: Active VLANs, Total VLANs
- ✅ VXLAN: VTEP IP, VNI, VNI Name
- ✅ EVPN: MAC VRF, RD, Route Target
- ✅ BGP: ASN, Router-ID, соседи, EVPN
- ✅ OSPF: Process ID, VRF, Router-ID, Areas, Networks
- ✅ VRF: Имя, описание
- ✅ Port-Channel: Номер, description, VLANs, LACP status
- ✅ LLDP: Соседи, description, chassis-id, port-id
- ✅ Статус интерфейсов: up/down

**Примеры устройств:**
- sp-net-spn-pr01 (Spine, BCOM_S4132U)
- sp-leaf-03 (Leaf, BCOM_S4148Q8U)
- sp-net-br-pr01 (Border Router, BCOM-MR350)

---

#### **Cisco** (версия шаблона: 2.1)
**Платформы:**
- Cisco IOS (ISR, ASR routers)
- Cisco IOS-XE (Catalyst 9000)
- Cisco NX-OS (Nexus data center)
- Cisco ASA (Firewall)

**Поддерживаемые серии:**
- **Catalyst:** C9200, C9300, C9400, C9500, C9600
- **Nexus:** N3000, N5000, N7000, N9000
- **ASA:** 5500-X, 2100

**Извлекаемая информация:**
- ✅ Устройства, VLAN, интерфейсы
- ✅ BGP, Port-Channel (EtherChannel)
- ✅ LLDP, статус интерфейсов
- ⚠️ VRF (требуется доработка)
- ⚠️ VXLAN/EVPN (требуется доработка)

---

#### **Huawei** (версия шаблона: 1.3)
**Платформы:**
- VRP (Versatile Routing Platform)
- CE Series (Data Center)
- NE Series (Carrier)
- S Series (Enterprise)
- USG (Firewall)

**Поддерживаемые серии:**
- **CE:** CE6800, CE8800 (Data Center)
- **NE:** NE40E, NE80E (Carrier Router)
- **S:** S5700, S6700, S7700 (Enterprise)
- **USG:** USG6000 (Firewall)

**Извлекаемая информация:**
- ✅ Устройства, VLAN, интерфейсы
- ✅ LLDP, статус интерфейсов
- ⚠️ BGP, OSPF, VRF (требуется тестирование)

---

#### **Juniper** (версия шаблона: 1.2)
**Платформы:**
- Junos OS
- QFX Series (Data Center)
- EX Series (Enterprise)
- MX Series (Carrier)
- SRX Series (Firewall)

**Извлекаемая информация:**
- ✅ Устройства, VLAN, интерфейсы
- ✅ LLDP, статус интерфейсов
- ⚠️ BGP, OSPF (требуется тестирование)

---

#### **MikroTik** (версия шаблона: 2.2)
**Платформы:**
- RouterOS v6/v7
- CCR (Cloud Core Router)
- CRS (Cloud Router Switch)
- RB (RouterBOARD)

**Извлекаемая информация:**
- ✅ Устройства, маршруты, интерфейсы
- ✅ BGP, OSPF
- ✅ LLDP, статус интерфейсов
- ❌ VXLAN (ограниченная поддержка)

---

#### **HPE/Aruba (Comware)** (версия шаблона: 2.1)
**Платформы:**
- Comware 7
- 5130, 5510, 5700, 5900 серии

**Извлекаемая информация:**
- ✅ Устройства, VLAN, интерфейсы
- ✅ BGP, Port-Channel (BAGG)
- ✅ LLDP, IRF (Intelligent Resilient Framework)
- ✅ Статус интерфейсов

---

### 🥈 **Уровень 2: Базовая поддержка**

#### **Arista** (версия шаблона: 1.2)
**Платформы:** EOS, DCS Series
**Возможности:** Устройства, VLAN, BGP, LLDP

#### **F5 BIG-IP** (версия шаблона: 1.2)
**Платформы:** TMOS, BIG-IP iSeries, VIPRION
**Возможности:** Устройства, VLAN, виртуальные серверы, пулы

#### **Fortinet** (версия шаблона: 1.1)
**Платформы:** FortiOS, FortiGate
**Возможности:** Устройства, интерфейсы, политики фаервола

#### **Palo Alto** (версия шаблона: 1.1)
**Платформы:** PAN-OS, PA-Series
**Возможности:** Устройства, зоны безопасности, правила

#### **Dell** (версия шаблона: 1.1)
**Платформы:** Dell Networking OS, N-Series, S-Series
**Возможности:** Устройства, VLAN, LLDP

#### **Aruba** (версия шаблона: 1.1)
**Платформы:** ArubaOS, Mobility Controllers
**Возможности:** Устройства, VLAN, беспроводные контроллеры

#### **Qtech** (версия шаблона: 1.0)
**Платформы:** QSW-3310, QSW-6910
**Возможности:** Устройства, VLAN, Port-Channel, LLDP

#### **D-Link** (версия шаблона: 1.0)
**Платформы:** MES3300, MES3710P, NIS3500
**Возможности:** Устройства, VLAN, LLDP

#### **TFortis** (версия шаблона: 1.0)
**Платформы:** NIS-3500 (D-Link OEM)
**Возможности:** Устройства, VLAN, LLDP, Ring Protection

#### **Unknown (OEM)** (версия шаблона: 1.0)
**Платформы:** Неопределённые устройства на базе D-Link/TFortis
**Возможности:** Устройства, VLAN, LLDP, Port Security

---

## 📊 Статистика извлечения данных (на примере B4COM)

| Тип данных | Количество | Пример |
|------------|------------|--------|
| Устройства | 11 | sp-net-spn-pr01, sp-leaf-03 |
| Физических связей | 19 | P2P линки /31 |
| Управленческих интерфейсов | 11 | eth0, 10.7.8.x/24 |
| VLAN (всего) | 436 | VLAN 301-530, 1100-1532 |
| VXLAN VNI | 436 | VNI 301-530, 1100-1532 |
| Port-Channel | 58 | po1-po56 с LACP |
| BGP сессий | 108 | EVPN соседи |
| LLDP соседей | 266 | На 11 устройствах |
| Интерфейсов up | 411 | Активные |
| Интерфейсов down | 238 | Неактивные/unused |

---

## 🔧 Добавление нового вендора

### Шаг 1: Создание JSON-шаблона

Создайте файл `patterns/devices/<vendor>.json`:

```json
{
  "vendor": "VendorName",
  "version": "1.0",
  "vendor_signatures": ["уникальные сигнатуры"],
  "detect_patterns": ["общие паттерны"],
  "name_patterns": [{"pattern": "...", "group": 1}],
  "model_patterns": [{"pattern": "...", "group": 1}],
  "type_inference": [
    {"any": ["ключевые слова"], "type": "switch", "score": 100}
  ],
  "default_device_type": "switch",
  "network_extraction_rules": {...},
  "bgp_extraction_rules": {...},
  "lldp_extraction_rules": {
    "enabled": true,
    "lldp_run_pattern": "^lldp run",
    "neighbor_description_pattern": "^\\s+description\\s+(.+)"
  },
  "interface_status_rules": {
    "enabled": true,
    "shutdown_pattern": "^\\s*shutdown\\s*$",
    "no_shutdown_pattern": "^\\s*no\\s+shutdown\\s*$"
  }
}
```

### Шаг 2: Валидация шаблона

```bash
python3 -c "
from lib.device_analyzer import VendorPatternLoader
loader = VendorPatternLoader('patterns/devices', validate=True)
patterns = loader.load_patterns()
"
```

### Шаг 3: Тестирование

Поместите тестовые конфигурации в `data_test/` и запустите:

```bash
python3 main.py
```

---

## 📝 История обновлений

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2026-03-12 | 1.3 (B4COM) | ✅ LLDP, ✅ Interface Status, ✅ VRF, ✅ OSPF |
| 2026-03-12 | 2.1 (Cisco) | ✅ LLDP, ✅ Interface Status |
| 2026-03-12 | 1.3 (Huawei) | ✅ LLDP, ✅ Interface Status |
| 2026-03-12 | 1.2 (Juniper) | ✅ LLDP, ✅ Interface Status |
| 2026-03-12 | 2.2 (MikroTik) | ✅ LLDP, ✅ Interface Status |
| 2026-03-12 | 1.2 (Arista) | ✅ LLDP, ✅ Interface Status |
| 2026-03-12 | 1.2 (F5) | ✅ LLDP, ✅ Interface Status |
| 2026-03-12 | 2.1 (HPE/Aruba) | ✅ Interface Status |
| 2026-03-12 | 1.0 (Qtech/DLink/TFortis) | ✅ Interface Status |

---

## 📞 Контакты и поддержка

- **GitHub Issues:** https://github.com/yourusername/netconf-parser/issues
- **Документация:** QWEN.md, Readme.md
