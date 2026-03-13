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
└── data/                       # Конфигурационные файлы
    └── *.cfg                
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
