# NetConf Parser & SEAF Converter

Система анализа конфигураций сетевого оборудования для автоматического построения топологий сети и конвертации в формат SEAF (System Enterprise Architecture Framework).

## 📌 Описание

Этот проект позволяет автоматически анализировать конфигурационные файлы сетевого оборудования разных производителей, извлекать структурированную информацию, строить сетевые топологии и конвертировать данные в формат SEAF для использования в системах архитектурного моделирования.

## 🚀 Основные возможности

### Анализ сетевого оборудования
- **Автоматическое определение вендора** по сигнатурам конфигурации
- **Извлечение данных устройства**: имя, модель, тип, VLAN, маршрутизируемые сети
- **Поддержка 9+ производителей**:
  - Cisco (IOS, NX-OS, ASA)
  - Juniper (Junos)
  - Huawei (Enterprise, Carrier)
  - MikroTik (RouterOS)
  - F5 (BIG-IP)
  - Arista (EOS)
  - Palo Alto Networks (PAN-OS)
  - Fortinet (FortiOS)
  - Aruba/HPE
  - Dell Networking

### Анализ топологии
- **Физические связи** (Physical P2P Links) — обнаружение соединений между устройствами
- **Управленческие сети** (Management Networks) — интерфейсы управления
- **Логические связи** (Logical Links) — VXLAN overlay, сервисные сети

### Визуализация
- **Генерация диаграмм draw.io** с использованием шаблонов
- **5 алгоритмов размещения**:
  - Круговой (circular)
  - Сеточный (grid)
  - Силовой (force-directed)
  - Кластерный (clustered)
  - Spine-Leaf (оптимально для CLOS-архитектур)

### SEAF Converter
- **Парсинг YAML-схем** из каталога `patterns/seaf/`
- **Поддержка наследования** через `allOf` (базовые сущности)
- **Поддержка вариантов** через `oneOf` (LAN/WAN)
- **Генерация шаблонов** для заполнения данными
- **Конвертация DRAWIO → YAML** для экспорта в SEAF

## 📂 Структура проекта

```
NetConf_Parser/
├── main.py                     # Точка входа
├── requirements.txt            # Зависимости
├── Readme.md                   # Документация
├── network_diagram.drawio      # Исходная диаграмма
├── network_details.txt         # Детальный отчёт
├── seaf.yaml                   # Экспортированные данные SEAF
│
├── lib/
│   ├── device_analyzer.py      # Анализ устройств и топологии
│   ├── network_visualizer.py   # Визуализация в draw.io
│   └── seaf_converter.py       # Конвертер SEAF схем
│
├── patterns/
│   ├── devices/                # Шаблоны вендоров (JSON)
│   │   ├── cisco.json
│   │   ├── juniper.json
│   │   ├── huawei.json
│   │   └── ...
│   ├── drawio/                 # Шаблоны draw.io
│   │   ├── base.drawio
│   │   └── templates/
│   │       ├── index.yaml
│   │       └── stencils.yaml
│   └── seaf/                   # YAML-схемы SEAF
│       ├── base_entity.yaml    # Базовые сущности
│       ├── network.yaml        # Сети (LAN/WAN)
│       ├── device.yaml         # Сетевые устройства
│       └── logical_link.yaml   # Логические связи
│
├── data/                       # Конфигурационные файлы
│   └── *.cfg
│
└── tests/
    ├── test_seaf_converter.py  # Тесты SEAF конвертера
    └── ...                     # Другие тесты
```

## 🛠 Требования

- Python 3.10+
- PyYAML (обработка YAML)
- N2G (работа с draw.io)
- pytest (тестирование)

## ⚙️ Установка

```bash
# Клонирование репозитория
git clone https://github.com/yourusername/netconf-parser.git
cd netconf-parser

# Создание виртуальной среды
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Установка зависимостей
pip install -r requirements.txt
```

## 🚀 Быстрый старт

### 1. Анализ конфигураций

Поместите конфигурационные файлы в папку `data/`:

```bash
mkdir data
cp /path/to/configs/*.cfg data/
```

Запустите анализ:

```bash
python3 main.py
```

### 2. Интерактивный режим

После анализа программа предложит:
- Выбрать алгоритм размещения для диаграммы
- Конвертировать данные из DRAWIO в YAML формат SEAF

```
Выберите алгоритм размещения объектов на диаграмме:
1. Круговой алгоритм
2. Сеточный алгоритм
3. Силовой алгоритм
4. Кластерный алгоритм
5. Spine-Leaf-Border Leaf (оптимально для CLOS архитектуры)

Произвести конвертацию данных из drawio файла? (Y/N): Y
```

## 📊 Примеры использования

### SEAF Converter: Получение словаря схем

```python
from lib.seaf_converter import get_seaf_dictionary

# Получить все схемы
schemas = get_seaf_dictionary()

# Структура:
# {
#   "network": {
#     "WAN": {...},
#     "LAN": {...}
#   },
#   "network_component": {...},
#   "logical_link": {...}
# }
```

### SEAF Converter: Заполнение шаблона данными устройства

```python
from lib.seaf_converter import get_seaf_dictionary, DeviceDataMapper

# Получить шаблон
schemas = get_seaf_dictionary()
template = schemas["network_component"]

# Данные устройства
devices = [
    {
        "device_name": "sw-core-01",
        "vendor": "Cisco",
        "model": "Nexus 9000",
        "device_type": "Маршрутизатор (роутер)",
    }
]

# Результаты анализа топологии
links_result = {
    "physical_links": [...],
    "mgmt_networks": [...],
    "logical_links": []
}

# Заполнить шаблон
filled = DeviceDataMapper.fill_network_component(
    template, "sw-core-01", devices, links_result,
    device_type="Межсетевой экран (файрвол)"  # опционально
)
```

### DrawioConverter: Конвертация DRAWIO → YAML

```python
from lib.seaf_converter import DrawioConverter

# Создать конвертер
converter = DrawioConverter()

# Конвертировать файл
converter.convert_drawio_to_yaml(
    "network_diagram.drawio",
    "seaf.yaml"
)

# Результат:
# seaf.company.ta.components.networks:
#   spb-ldc-leaf-sw-01:
#     model: CE6881-48S6CQ
#     type: Коммутатор (свитч)
#     OID: spb-ldc-leaf-sw-01
#     schema: seaf.company.ta.components.networks
```

### DrawioConverter: Извлечение объектов

```python
from lib.seaf_converter import DrawioConverter

converter = DrawioConverter()
objects = converter.extract_objects_from_drawio("network_diagram.drawio")

# objects = {
#   "seaf.company.ta.components.networks": {
#     "spb-ldc-leaf-sw-01": {...},
#     ...
#   },
#   "seaf.company.ta.services.networks": {
#     "192_168_201_0_31": {...},
#     ...
#   }
# }
```

## 🧩 Архитектура SEAF схем

### Базовая сущность (`base_entity.yaml`)

Определяет общие поля для всех сервисов:

```yaml
seaf.company.ta.services.base.entity:
  properties:
    title: string
    description: string
    app_components: array
    stand: array
    external_id: string
```

### Сети (`network.yaml`)

Поддерживает варианты LAN и WAN:

```yaml
patternProperties:
  "^([a-zA-Z0-9_-]+)(\\.[a-zA-Z0-9_-]+)+$":
    allOf:
      - $ref: "#/$defs/seaf.company.ta.services.base.entity"
    oneOf:
      - $ref: "#/$defs/seaf.company.ta.services.networks/wan"
      - $ref: "#/$defs/seaf.company.ta.services.networks/lan"
```

**Результат:**
```json
{
  "network": {
    "WAN": {
      "title": "",
      "type": "WAN",
      "wan_ip": "",
      "provider": "",
      ...
    },
    "LAN": {
      "title": "",
      "type": "LAN",
      "lan_type": ["Проводная", "Беспроводная"],
      "vlan": 0,
      ...
    }
  }
}
```

### Устройства (`device.yaml`)

Прямое определение свойств:

```yaml
patternProperties:
  "^([a-zA-Z0-9_-]+)(\\.[a-zA-Z0-9_-]+)+$":
    allOf:
      - $ref: "#/$defs/seaf.company.ta.services.base.entity"
      - $ref: "#/$defs/network_component_dzo"
    properties:
      type: {enum: [...]}
      model: {type: string}
      ...
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest tests/ -v

# Запуск тестов SEAF конвертера
pytest tests/test_seaf_converter.py -v
```

**Статистика тестов:**
- 59 тестов
- Покрытие: SchemaLoader, SchemaResolver, SchemaDictionaryBuilder, SeafConverter, DeviceDataMapper, DrawioConverter

## 📝 Форматы данных

### Структура links_result

```python
{
    "physical_links": [
        [dev1, vendor1, type1, intf1, ip1, dev2, vendor2, type2, intf2, ip2, network]
    ],
    "mgmt_networks": [
        [device, vendor, dev_type, intf, ip, network]
    ],
    "logical_links": [
        [dev1, vendor1, type1, intf_ip1, dev2, vendor2, type2, intf_ip2, desc]
    ]
}
```

### Структура seaf.yaml

```yaml
seaf.company.ta.components.networks:
  <OID или ID устройства>:
    title: string
    description: string
    type: string | [enum values]
    model: string
    network_connection: [normalized networks]
    OID: string
    schema: seaf.company.ta.components.networks

seaf.company.ta.services.networks:
  <OID или ID сети>:
    title: string
    type: LAN | WAN
    ipnetwork: string  # для LAN
    wan_ip: string     # для WAN
    OID: string
    schema: seaf.company.ta.services.networks
```

## 🔧 Расширение функциональности

### Добавление нового вендора

Создайте JSON-файл в `patterns/devices/`:

```json
{
  "vendor": "NewVendor",
  "version": "1.0",
  "vendor_signatures": ["уникальные сигнатуры"],
  "detect_patterns": ["общие паттерны"],
  "name_patterns": [{"pattern": "...", "group": 1}],
  "model_patterns": [{"pattern": "...", "group": 1}],
  "type_inference": [
    {"any": ["ключевые слова"], "type": "router", "score": 100}
  ],
  "network_extraction_rules": {...}
}
```

### Добавление новой SEAF-сущности

Создайте YAML-файл в `patterns/seaf/`:

```yaml
entities:
  seaf.company.ta.new_entity:
    title: Новая сущность
    objects:
      new_object:
        route: "/"
        title: Новый объект
    schema:
      $defs: {...}
      patternProperties: {...}
```

## 📋 Выходные файлы

| Файл | Описание |
|------|----------|
| `network_details.txt` | Детальный отчёт об анализе |
| `network_diagram.drawio` | Диаграмма топологии |
| `seaf.yaml` | Экспортированные данные SEAF |

## 📞 Контакты

- **GitHub**: https://github.com/yourusername/netconf-parser
- **Issues**: https://github.com/yourusername/netconf-parser/issues

## 📄 Лицензия

MIT License
