import re
import csv
import glob
from pathlib import Path
from bs4 import BeautifulSoup


def clean_text(text):
    """Самая важная функция: склеивает переносы, убирает мусор."""
    if not text: return ''
    text = text.replace('\xa0', ' ')
    # Убираем мягкие переносы и обычные дефисы, если они в конце строки перед пробелом
    text = text.replace('\xad', '')
    text = re.sub(r'[-‐‑]\s+', '', text)
    # Убираем лишние пробелы
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_page_numbers(content):
    """Достает номера страниц из ID дивов."""
    matches = re.findall(r'page(\d+)-div', content)
    return sorted(list(set(matches)), key=int)


def parse_plant_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Проверка на "биологическую состоятельность"
    if not re.search(r'[a-zA-Z]', content):
        return None

    soup = BeautifulSoup(content, 'html.parser')

    # 2. Номера страниц
    pages = get_page_numbers(content)

    # 3. Извлекаем все элементы с координатами для сортировки
    data_points = []
    for p in soup.find_all('p'):
        style = p.get('style', '')
        top_m = re.search(r'top:(\d+)px', style)
        left_m = re.search(r'left:(\d+)px', style)
        if top_m and left_m:
            data_points.append({
                'top': int(top_m.group(1)),
                'left': int(left_m.group(1)),
                'text': clean_text(p.get_text()),
                'is_bold': bool(p.find('b'))
            })

    # Сортировка: сначала левая колонка (left < 430), потом правая.
    # Внутри колонок - сверху вниз.
    data_points.sort(key=lambda x: (1 if x['left'] >= 430 else 0, x['top']))

    # 4. Ищем названия (жирные строки в начале)
    russian_name = ''
    latin_name = ''
    family = ''

    for pt in data_points:
        txt = pt['text']
        if pt['is_bold'] and not russian_name and re.search(r'[А-ЯЁ]', txt):
            russian_name = txt
            continue
        if pt['is_bold'] and russian_name and not latin_name and re.search(r'[a-zA-Z]', txt):
            latin_name = txt
            continue
        if 'Семейство' in txt and not family:
            family = txt.replace('Семейство', '').strip(' —:')

    # 5. Парсинг разделов
    header_map = {
        'Категория и статус': 'category',
        'Распространение': 'distribution',
        'Места обитания': 'habitat',
        'Численность': 'abundance',
        'Лимитирующие факторы': 'limiting_factors',
        'Принятые меры охраны': 'protection_measures',
        'Необходимые дополнительные': 'additional_measures',
        'Автор': 'author'
    }

    result = {field: [] for field in header_map.values()}
    current_field = None

    for pt in data_points:
        txt = pt['text']
        # Проверка на заголовок (жирный и есть в словаре)
        for hdr, field in header_map.items():
            if hdr in txt:
                current_field = field
                # Чистим сам заголовок из текста
                txt = txt.replace(hdr, '').strip('. ')
                break

        if current_field and txt:
            result[current_field].append(txt)

    # 6. Род (из первого слова латыни)
    genus = latin_name.split()[0] if latin_name else ''

    return {
        'page': '; '.join(pages),
        'russian_name': russian_name,
        'latin_name': latin_name,
        'family': family,
        'genus': genus,
        **{k: ' '.join(v) for k, v in result.items()}
    }


def main():
    # УКАЖИ ПУТЬ К ТВОЕЙ ПАПКЕ С НАРЕЗАННЫМИ ФАЙЛАМИ
    input_folder = Path('/Users/evgeniashemina/Desktop/final_plants/splited_plants_final')
    output_csv = Path('/Users/evgeniashemina/Desktop/final_plants/FINAL_CLEAN_DATASET_plants_11.csv')

    files = sorted(list(input_folder.glob('*.html')))
    all_records = []

    print(f"Найдено файлов для обработки: {len(files)}")

    for f in files:
        rec = parse_plant_file(f)
        if rec:
            all_records.append(rec)

    # Запись CSV
    keys = ['page', 'russian_name', 'latin_name', 'family', 'genus', 'category',
            'distribution', 'habitat', 'abundance', 'limiting_factors',
            'protection_measures', 'additional_measures', 'author']

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"Готово! Сохранено {len(all_records)} видов в {output_csv}")


if __name__ == "__main__":
    main()