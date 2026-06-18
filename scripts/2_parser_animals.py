import re
import csv
import glob
from pathlib import Path


def clean_html_tags(text):
    if not text:
        return ''
    # 1. Принудительно вычищаем текстовые сущности неразрывного пробела, которые ломали отображение
    text = text.replace('&#160;', ' ').replace('&nbsp;', ' ')

    # 2. Заменяем ВСЕ HTML-теги на пробелы, чтобы слова на стыках форматирования (например, после <b>)
    # никогда не склеивались впритык друг к другу
    text = re.sub(r'<[^>]+>', ' ', text)
    return text


def global_linear_clean(text):
    if not text:
        return ''
    # Очищаем от остаточных скрытых символов переноса и спецкодов
    text = text.replace('\xa0', ' ').replace('\xad', '')

    # Склеиваем слова, которые были разорваны дефисами при переносе на новую строку (числен- ности -> численности)
    text = re.sub(r'(\w+)[-‐‑]\s+(\w+)', r'\1\2', text)

    # КЛЮЧЕВОЙ ШАГ: Находим любые последовательности пробелов, табов, а также символов
    # переноса строк (\n, \r) и СЖИМАЕМ их в один обычный пробел.
    # Это полностью убирает дефект "текста через одну строку" и делает абзац сплошным.
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def parse_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Нормализуем переносы: превращаем блочные разрывы в стандартный символ новой строки \n
    content = re.sub(r'</p>|</div>|<br\s*/?>', '\n', content)
    lines = content.split('\n')

    # Поиск номера страницы
    page_match = re.search(r'<a name=(\d+)>', content)
    page = page_match.group(1) if page_match else Path(filepath).stem.split('_')[0]

    russian_name = ""
    latin_name = ""
    family = ""

    # 1. Извлечение Латыни, Русского названия и Семейства
    for i, line in enumerate(lines):
        if '<i>' in line and re.search(r'[A-Za-z]', line) and not latin_name:
            lat_match = re.search(r'<i>(.*?)</i>', line)
            if lat_match:
                latin_name = global_linear_clean(clean_html_tags(lat_match.group(1)))

            clean_line = clean_html_tags(line).replace(latin_name, '').strip(' ,.;:-')
            if clean_line and re.search(r'[А-Яа-я]', clean_line):
                russian_name = global_linear_clean(clean_line)
            elif i > 0:
                russian_name = global_linear_clean(clean_html_tags(lines[i - 1])).strip(' ,.;:-')

        if 'Семейство' in line and not family:
            fam_match = re.search(r'Семейство\s+([А-Яа-яёЁ\s–-]+)', clean_html_tags(line))
            if fam_match:
                family = global_linear_clean(fam_match.group(1))

    # 2. Карта соответствия заголовков разделов
    headers_map = {
        'Категория': 'category',
        'Распространение': 'distribution',
        'Места обитания': 'habitat',
        'Численность': 'abundance',
        'Лимитирующие факторы': 'limiting_factors',
        'Принятые меры': 'protection_measures',
        'Необходимые дополнительные': 'additional_measures',
        'Автор': 'author',
        'Составител': 'author'
    }

    results = {k: [] for k in headers_map.values()}
    current_field = None

    # 3. Линейный сбор сырых строк по секциям
    for line in lines:
        clean_l = clean_html_tags(line).strip()
        if not clean_l:
            continue

        is_header = False

        # Если в строке есть <b> — это маркер начала нового раздела
        if '<b>' in line:
            for h_key, f_key in headers_map.items():
                if h_key.lower() in clean_l.lower() and len(clean_l) < 150:
                    current_field = f_key
                    is_header = True
                    # Вырезаем сам заголовок из полезного текста ячейки
                    clean_l = re.sub(rf'(?i){h_key}[^.]*\.?', '', clean_l).strip()
                    break

        if not is_header and re.search(r'(?i)(Автор[ы]?-составител|Составител)', clean_l):
            current_field = 'author'
            clean_l = re.sub(r'(?i)(Автор[ы]?-составител[ьяи]|Составител[ьи])[.:\s]*', '', clean_l).strip()

        # Складываем строчки как есть, пока не встретим новый заголовок
        if current_field and clean_l:
            results[current_field].append(clean_l)

    # 4. Финальная склейка "встык" и тотальное уничтожение межстрочных разрывов
    final_data = {}
    for k, v in results.items():
        # Склеиваем массив строк через пробел
        raw_joined = ' '.join(v)
        # Прогоняем весь получившийся монолитный текст через глобальный сжиматель
        final_data[k] = global_linear_clean(raw_joined)

    # 5. Очистка от мусорных заголовков внутри ячеек (как в томе растений)
    final_data['habitat'] = re.sub(r'^(и особенности экологии)[.,\s]*', '', final_data['habitat'], flags=re.IGNORECASE)
    final_data['additional_measures'] = re.sub(r'^(меры охраны|необходимые дополнительные меры охраны)[.,\s]*', '',
                                               final_data['additional_measures'], flags=re.IGNORECASE)

    # 6. Извлечение кодов категорий и нормализация авторов по маске
    category_raw = final_data['category']
    cat_num_match = re.search(r'\b([0-5])\b', category_raw)
    category_numeric = cat_num_match.group(1) if cat_num_match else ''
    codes = re.findall(r'\b(У|III|II|I|КР|НО|НД|БУ|И)\b', category_raw)
    category_text = ', '.join(sorted(set(codes)))

    author_raw = final_data['author']
    author_matches = re.findall(r'[А-Я]\.[А-Я]\.\s*[А-Я][а-я]+', author_raw)
    author = ', '.join(author_matches) if author_matches else author_raw.strip(' ,.-')

    genus = latin_name.split()[0] if latin_name else ''

    # 7. Формирование строки датасета (14 унифицированных полей)
    return {
        'latin_name': latin_name,
        'page': page,
        'russian_name': russian_name,
        'family': family,
        'genus': genus,
        'category_numeric': category_numeric,
        'category_text': category_text,
        'distribution': final_data['distribution'],
        'habitat': final_data['habitat'],
        'abundance': final_data['abundance'],
        'limiting_factors': final_data['limiting_factors'],
        'protection_measures': final_data['protection_measures'],
        'additional_measures': final_data['additional_measures'],
        'author': author
    }


def process_all_files(input_folder, output_csv):
    html_files = glob.glob(str(Path(input_folder) / '*.html'))
    all_records = []
    seen_latin = set()

    print(f"Найдено {len(html_files)} файлов для парсинга.")

    for file_path in sorted(html_files):
        try:
            record = parse_file(file_path)
            if record and record['latin_name']:
                if record['latin_name'] not in seen_latin:
                    all_records.append(record)
                    seen_latin.add(record['latin_name'])
        except Exception as e:
            print(f"Ошибка в файле {Path(file_path).name}: {e}")

    if not all_records:
        print("❌ Нет данных для сохранения.")
        return

    fieldnames = [
        'latin_name', 'page', 'russian_name', 'family', 'genus',
        'category_numeric', 'category_text', 'distribution', 'habitat',
        'abundance', 'limiting_factors', 'protection_measures',
        'additional_measures', 'author'
    ]

    with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"✅ УСПЕХ! Рваные строки склеены. Создан идеальный CSV: {len(all_records)} видов.")


if __name__ == '__main__':
    INPUT_DIR = '/Users/evgeniashemina/Desktop/final_animals/splited_animals_final'
    OUTPUT_CSV = '/Users/evgeniashemina/Desktop/final_animals/RED_BOOK_ANIMALS_FINAL.csv'

    process_all_files(INPUT_DIR, OUTPUT_CSV)