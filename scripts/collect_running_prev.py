#!/usr/bin/env python3
"""
Скрипт для поиска, обработки и перемещения файлов running.prev

Рекурсивно ищет файлы с именем running.prev в указанном каталоге,
переименовывает их в <ИМЯ_КАТАЛОГА>.prev, удаляет чувствительные данные
и перемещает в целевой каталог.
"""

import os
import shutil
import argparse
from pathlib import Path


def filter_sensitive_lines(content: str) -> str:
    """
    Удаляет строки, содержащие чувствительные данные.
    
    Args:
        content: Исходное содержимое файла
        
    Returns:
        Содержимое без чувствительных строк
    """
    sensitive_patterns = [
        "enable secret",
        "username"
    ]
    
    lines = content.splitlines()
    filtered_lines = []
    
    for line in lines:
        # Проверяем, содержит ли строка чувствительные данные
        is_sensitive = False
        for pattern in sensitive_patterns:
            if pattern in line:
                is_sensitive = True
                break
        
        # Добавляем строку только если она не чувствительная
        if not is_sensitive:
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)


def find_running_prev_files(source_dir: Path) -> list[Path]:
    """
    Рекурсивно ищет файлы running.prev в каталоге.
    
    Args:
        source_dir: Исходный каталог для поиска
        
    Returns:
        Список найденных файлов
    """
    found_files = []
    
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file == "running.prev":
                found_files.append(Path(root) / file)
    
    return found_files


def process_file(source_file: Path, dest_dir: Path, dry_run: bool = False) -> dict:
    """
    Обрабатывает单个 файл: переименовывает, фильтрует и перемещает.
    
    Args:
        source_file: Путь к исходному файлу
        dest_dir: Целевой каталог
        dry_run: Если True, только показывает что будет сделано без реальных действий
        
    Returns:
        Словарь с результатами обработки
    """
    result = {
        'source': str(source_file),
        'dest': None,
        'status': 'pending',
        'error': None,
        'lines_removed': 0
    }
    
    # Получаем имя родительского каталога
    parent_dir_name = source_file.parent.name
    new_filename = f"{parent_dir_name}.prev"
    dest_file = dest_dir / new_filename
    
    result['dest'] = str(dest_file)
    
    if dry_run:
        result['status'] = 'dry_run'
        return result
    
    try:
        # Читаем исходный файл
        with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
            original_content = f.read()
        
        original_lines = len(original_content.splitlines())
        
        # Фильтруем чувствительные данные
        filtered_content = filter_sensitive_lines(original_content)
        filtered_lines = len(filtered_content.splitlines())
        
        result['lines_removed'] = original_lines - filtered_lines
        
        # Создаем целевой каталог если не существует
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Записываем обработанный контент
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(filtered_content)
        
        result['status'] = 'success'
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(
        description='Поиск, обработка и перемещение файлов running.prev',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s -s /path/to/configs -d /path/to/output
  %(prog)s -s ./data -d ./collected_configs --dry-run
  %(prog)s -s /configs -d /backup --verbose
        """
    )
    
    parser.add_argument(
        '-s', '--source',
        type=Path,
        required=True,
        help='Исходный каталог для поиска файлов running.prev'
    )
    
    parser.add_argument(
        '-d', '--destination',
        type=Path,
        required=True,
        help='Целевой каталог для перемещения обработанных файлов'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Режим "сухого запуска" - показывает что будет сделано без реальных изменений'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Подробный вывод информации о процессе'
    )
    
    args = parser.parse_args()
    
    # Валидация исходного каталога
    if not args.source.exists():
        print(f"❌ Ошибка: Исходный каталог не найден: {args.source}")
        return 1
    
    if not args.source.is_dir():
        print(f"❌ Ошибка: Указанный путь не является каталогом: {args.source}")
        return 1
    
    # Поиск файлов
    print(f"🔍 Поиск файлов running.prev в каталоге: {args.source}")
    found_files = find_running_prev_files(args.source)
    
    if not found_files:
        print("⚠️  Файлы running.prev не найдены")
        return 0
    
    print(f"✅ Найдено файлов: {len(found_files)}\n")
    
    # Обработка файлов
    results = []
    success_count = 0
    error_count = 0
    total_lines_removed = 0
    
    for file_path in found_files:
        result = process_file(file_path, args.destination, args.dry_run)
        results.append(result)
        
        if result['status'] == 'success':
            success_count += 1
            total_lines_removed += result['lines_removed']
            
            if args.verbose:
                print(f"✅ {result['source']}")
                print(f"   → {result['dest']}")
                print(f"   Удалено строк: {result['lines_removed']}")
                
        elif result['status'] == 'dry_run':
            if args.verbose:
                print(f"📋 {result['source']}")
                print(f"   → {result['dest']} (будет перемещено)")
                
        else:
            error_count += 1
            if args.verbose:
                print(f"❌ {result['source']}")
                print(f"   Ошибка: {result['error']}")
    
    # Вывод итогов
    print("\n" + "=" * 70)
    print("📊 ИТОГИ:")
    print("=" * 70)
    
    if args.dry_run:
        print(f"Режим: СУХОЙ ЗАПУСК (изменения не вносились)")
    else:
        print(f"Режим: ОБРАБОТКА")
    
    print(f"Найдено файлов:      {len(found_files)}")
    print(f"Успешно обработано:  {success_count}")
    print(f"Ошибок:              {error_count}")
    print(f"Удалено строк:       {total_lines_removed}")
    print(f"Целевой каталог:     {args.destination}")
    print("=" * 70)
    
    # Вывод списка обработанных файлов
    if args.verbose and results:
        print("\n📁 Обработанные файлы:")
        print("-" * 70)
        for result in results:
            status_icon = "✅" if result['status'] == 'success' else "📋" if result['status'] == 'dry_run' else "❌"
            print(f"{status_icon} {os.path.basename(result['source']):<30} → {os.path.basename(result['dest'])}")
            if result['lines_removed'] > 0:
                print(f"   (удалено строк: {result['lines_removed']})")
    
    return 0 if error_count == 0 else 1


if __name__ == '__main__':
    exit(main())
