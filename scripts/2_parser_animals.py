import re
import csv
import glob
from pathlib import Path
from bs4 import BeautifulSoup


def clean_text(text):
    if not text:
        return ''
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'!+', '', text)
    text = re.sub(r'\s+\d+$', '', text)
    return text.strip()


def parse_animal_file(file_path, debug=False):
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # ---- Русское название ----
    russian_name = ''
    for p in soup.find_all('p', class_='ft028'):
        text = p.get_text().strip()
        if re.search('[а-яА-Я]', text) and not re.search('[a-zA-Z]', text):
            russian_name = clean_text(text)
            break

    # ---- Латинское название ----
    latin_name = ''
    for p in soup.find_all('p', class_='ft029'):
        text = p.get_text().strip()
        latin_name = clean_text(text)
        break

    # ---- Отряд и семейство ----
    family = ''
    for p in soup.find_all('p', class_='ft031'):
        text = p.get_text().strip()
        f_match = re.search(r'Семейство\s+([А-Яа-яёЁ\s–-]+)', text)
        if f_match:
            family = clean_text(f_match.group(1)).strip(' –-')
        break

    # ---- Поиск заголовков (Авторы исключены из заголовков!) ----
    all_ps = soup.find_all('p')

    header_map = {
        'категория и статус': 'category',
        'категория': 'category',
        'распространение': 'distribution',
        'места обитания': 'habitat',
        'особенности экологии': 'habitat',
        'численность': 'abundance',
        'лимитирующие факторы': 'limiting_factors',
        'принятые меры': 'protection_measures',
        'дополнительные меры': 'additional_measures',
        'необходимые': 'additional_measures'
    }

    header_indices = []
    header_fields = []

    for i, p in enumerate(all_ps):
        classes = p.get('class', [])
        text_lower = p.get_text().lower().replace('-\n', '').replace('- ', '').strip()

        if 'ft011' in classes or (len(text_lower) > 3 and len(text_lower) < 45):
            for key, field in header_map.items():
                if key in text_lower and field not in header_fields:
                    header_indices.append(i)
                    header_fields.append(field)
                    break

    # ---- Извлекаем текст разделов ----
    result = {field: '' for field in header_map.values()}
    result['author'] = ''  # Инициализируем пустую колонку автора

    for idx, start_i in enumerate(header_indices):
        end_i = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(all_ps)
        field = header_fields[idx]

        lines = []
        for i in range(start_i + 1, end_i):
            p = all_ps[i]

            text = clean_text(p.get_text())
            if not text or re.match(r'^\d+$', text):
                continue

            style = p.get('style', '')
            top_match = re.search(r'top:(\d+)px', style)
            left_match = re.search(r'left:(\d+)px', style)

            page_div = p.find_parent('div')
            page_id = page_div.get('id', '') if page_div else ''
            p_match = re.search(r'\d+', page_id)
            page_num = int(p_match.group()) if p_match else 0

            if top_match and left_match:
                top = int(top_match.group(1))
                left = int(left_match.group(1))
                lines.append((page_num, top, left, text))

        # СУПЕР-УМНАЯ 4D-СОРТИРОВКА
        CENTER_X = 350
        lines.sort(key=lambda x: (
            x[0],
            0 if x[2] < CENTER_X else 1,
            x[1] // 10,
            x[2]
        ))

        section_text = ''
        for page_num, top, left, text in lines:
            if not text:
                continue
            if section_text.endswith('-'):
                section_text = section_text[:-1] + text
            else:
                if section_text and not text.startswith(('.', ',', ';', ':', '!', '?')):
                    section_text += ' '
                section_text += text

        result[field] = clean_text(section_text)

    # ==========================================
    # ИДЕАЛЬНАЯ ЛОГИКА ДЛЯ КАТЕГОРИЙ
    # ==========================================
    cat_raw = result.get('category', '')

    for i, p in enumerate(all_ps):
        if i in header_indices:
            idx = header_indices.index(i)
            if header_fields[idx] == 'category':
                cat_raw = p.get_text() + ' ' + cat_raw
                break

    cat_num = re.search(r'\b([0-5])\b', cat_raw)
    category_numeric = cat_num.group(1) if cat_num else ''

    letters = []
    for code in ['КР', 'ИЗ', 'НД', 'БУ', 'ВО', 'НО']:
        if re.search(r'\b' + code + r'\b', cat_raw):
            letters.append(code)

    if re.search(r'\bУ\b\s*[–-]', cat_raw) or 'уязвим' in cat_raw.lower():
        letters.append('У')

    romans = re.findall(r'\b(III|II|I)\b', cat_raw)

    final_codes = []
    for code in letters + romans:
        if code not in final_codes:
            final_codes.append(code)

    category_text = ', '.join(final_codes)

    # ==========================================
    # ИДЕАЛЬНАЯ ЛОГИКА АВТОРОВ (Строго 2 условия)
    # ==========================================
    author_text_raw = ""

    # Ищем авторов во всех собранных текстовых блоках
    for field in list(result.keys()):
        if field == 'author':
            continue

        text = result[field]
        if not text:
            continue

        # 1. Отсекаем литературу
        lit_match = re.search(r'(?i)\b(?:литератур[аеыу]|источники|основная литература)\b', text)
        if lit_match:
            text = text[:lit_match.start()]

        # 2. Ищем строгое слово "Автор-составитель" или "Авторы-составители"
        auth_match = re.search(r'(?i)Автор[ы]?\s*-\s*составител[ьи][\.\:]?\s*', text)
        if auth_match:
            # Забираем всё, что идет ПОСЛЕ слова "автор-составитель"
            author_text_raw = text[auth_match.end():]
            # А из исходного поля (например, "меры охраны") удаляем этот кусок
            text = text[:auth_match.start()]

        result[field] = text.strip()

    # 3. Применяем жесткую регулярку ФИО к найденному куску текста
    if author_text_raw:
        # Паттерн: Инициалы (1 или 2) + Фамилия С БОЛЬШОЙ БУКВЫ (исключает D. middendorffi)
        fio_pattern = r'[А-ЯЁA-Z]\.\s*(?:[А-ЯЁA-Z]\.\s*)?[А-ЯЁA-Z][а-яёa-z]+(?:-[А-ЯЁA-Z][а-яёa-z]+)?'
        author_matches = re.findall(fio_pattern, author_text_raw)

        unique_authors = []
        for a in author_matches:
            # Чистим пробелы для идеального формата "А.В. Иванов"
            clean_a = a.replace(' ', '')
            clean_a = re.sub(r'\.([А-ЯЁA-Z])', r'. \1', clean_a)
            clean_a = re.sub(r'([А-ЯЁA-Z]\.)\s*([А-ЯЁA-Z]\.)', r'\1\2', clean_a)

            if clean_a not in unique_authors:
                unique_authors.append(clean_a)

        result['author'] = ', '.join(unique_authors)

    # ---- Род и Номер страницы ----
    genus = ''
    if latin_name:
        genus_match = re.match(r'([A-Z][a-z]+)', latin_name)
        genus = genus_match.group(1) if genus_match else ''

    page_num = ''
    page_comment = soup.find(string=re.compile(r'Page \d+'))
    if page_comment:
        page_match = re.search(r'Page (\d+)', page_comment)
        if page_match:
            page_num = page_match.group(1)
    if not page_num:
        name = Path(file_path).stem
        num_match = re.search(r'^\d+', name)
        if num_match:
            page_num = num_match.group(0)

    if debug:
        print(f"\n[DEBUG] Файл: {Path(file_path).name}")
        print(f"Категория цифра: {category_numeric}")
        print(f"Категория текст: {category_text}")
        print(f"Авторы: {result['author']}")

    return {
        'page': page_num,
        'russian_name': russian_name,
        'latin_name': latin_name,
        'family': family,
        'genus': genus,
        'category_numeric': category_numeric,
        'category_text': category_text,
        'distribution': result.get('distribution', ''),
        'habitat': result.get('habitat', ''),
        'abundance': result.get('abundance', ''),
        'limiting_factors': result.get('limiting_factors', ''),
        'protection_measures': result.get('protection_measures', ''),
        'additional_measures': result.get('additional_measures', ''),
        'author': result.get('author', '')
    }


def process_all_html_files(input_folder, output_csv, debug_file=None):
    html_files = glob.glob(str(Path(input_folder) / '*.html'))
    if not html_files:
        print(f"В папке {input_folder} нет .html файлов.")
        return

    all_records = []
    for file_path in sorted(html_files):
        debug = (debug_file and Path(file_path).name == debug_file)
        record = parse_animal_file(file_path, debug=debug)

        if record and (record['russian_name'] or record['latin_name']):
            all_records.append(record)

    if not all_records:
        print("Нет данных для сохранения.")
        return

    fieldnames = [
        'page', 'russian_name', 'latin_name', 'family', 'genus',
        'category_numeric', 'category_text', 'distribution', 'habitat',
        'abundance', 'limiting_factors', 'protection_measures',
        'additional_measures', 'author'
    ]

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for record in all_records:
            writer.writerow(record)

    print(f"Готово! Сохранено {len(all_records)} записей в {output_csv}")


if __name__ == '__main__':
    INPUT_DIR = '/Users/evgeniashemina/Desktop/final_animals/splited_animals'
    OUTPUT_CSV = '/Users/evgeniashemina/Desktop/final_animals/parsed_animals_25.06_7.csv'

    process_all_html_files(INPUT_DIR, OUTPUT_CSV)