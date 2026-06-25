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
            family = clean_text(f_match.group(1))
        break

    # ---- Все теги p ----
    all_ps = soup.find_all('p')

    # ---- Находим заголовки разделов ----
    header_map = {
        'Категория и статус': 'category',
        'Распространение': 'distribution',
        'Места обитания и особенности экологии': 'habitat',
        'Места обитания и особенности эколо- гии': 'habitat',
        'Численность': 'abundance',
        'Лимитирующие факторы': 'limiting_factors',
        'Принятые меры охраны': 'protection_measures',
        'Необходимые дополнительные меры охраны': 'additional_measures',
        'Автор-составитель': 'author'
    }

    # Индексы заголовков
    header_indices = []
    header_fields = []
    for i, p in enumerate(all_ps):
        if 'ft011' in p.get('class', []):
            htext = p.get_text().strip()
            htext = re.sub(r'\s*\.\s*$', '', htext)
            for hdr, field in header_map.items():
                if hdr in htext or htext in hdr:
                    header_indices.append(i)
                    header_fields.append(field)
                    break

    # Если не нашли все, попробуем более свободный поиск
    if len(header_indices) < 8:
        header_indices = []
        header_fields = []
        for i, p in enumerate(all_ps):
            text = p.get_text().strip()
            if 'Распространение' in text and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('distribution')
            elif 'Категория' in text and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('category')
            elif 'Численность' in text and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('abundance')
            elif 'Лимитирующие' in text and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('limiting_factors')
            elif 'Принятые' in text and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('protection_measures')
            elif 'Необходимые' in text and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('additional_measures')
            elif 'Автор' in text and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('author')
            elif ('Места обитания' in text or 'эколо- гии' in text) and 'ft011' in p.get('class', []):
                header_indices.append(i)
                header_fields.append('habitat')
        # Сортируем по top (нужно получить координаты)
        # Упростим: оставим как есть, порядок может быть не идеален, но текст не перемешается

    # Извлекаем текст разделов
    result = {field: '' for field in header_map.values()}
    for idx, start_i in enumerate(header_indices):
        end_i = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(all_ps)
        field = header_fields[idx] if idx < len(header_fields) else None
        if not field:
            continue
        # Собираем строки ft07 между start_i и end_i
        lines = []
        for i in range(start_i + 1, end_i):
            p = all_ps[i]
            if 'ft07' not in p.get('class', []):
                continue
            text = p.get_text().replace('\xa0', ' ')
            text = clean_text(text)
            if not text or re.match(r'^\d+$', text):
                continue
            style = p.get('style', '')
            top_match = re.search(r'top:(\d+)px', style)
            left_match = re.search(r'left:(\d+)px', style)
            if top_match and left_match:
                top = int(top_match.group(1))
                left = int(left_match.group(1))
                lines.append((top, left, text))
        # Сортируем по top, left
        lines.sort(key=lambda x: (x[0], x[1]))
        # Склеиваем
        section_text = ''
        prev = ''
        for top, left, text in lines:
            if prev:
                if prev.endswith('-'):
                    section_text = section_text.rstrip('-')
                elif not text.startswith(('.', ',', ';', ':', '!', '?')):
                    section_text += ' '
            section_text += text
            prev = text
        result[field] = clean_text(section_text)

    # ---- Категория ----
    cat_raw = result.get('category', '')
    cat_num = re.search(r'\b([0-5])\b', cat_raw)
    category_numeric = cat_num.group(1) if cat_num else ''
    codes = re.findall(r'\b(У|III|II|I|КР|НО|НД|БУ)\b', cat_raw)
    category_text = ', '.join(set(codes))

    # ---- Род ----
    genus = ''
    if latin_name:
        genus_match = re.match(r'([A-Z][a-z]+)', latin_name)
        genus = genus_match.group(1) if genus_match else ''

    # ---- Номер страницы ----
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
        print(f"\nDEBUG {Path(file_path).name}")
        print(f"Distribution: {result.get('distribution', '')[:300]}")

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
        print(f"Обработка: {Path(file_path).name}")
        debug = (debug_file and Path(file_path).name == debug_file)
        record = parse_animal_file(file_path, debug=debug)
        if record and record['russian_name']:
            all_records.append(record)
        else:
            print(f"  Не удалось извлечь данные для {Path(file_path).name}")

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

    print(f"Сохранено {len(all_records)} записей в {output_csv}")


if __name__ == '__main__':
    INPUT_DIR = '/Users/evgeniashemina/Desktop/final_plants/plants_splited'
    OUTPUT_CSV = '/Users/evgeniashemina/Desktop/final_animals/red_book_plants_final_10.csv'
    DEBUG_FILE = None  # '267_Дальневосточный_аист.html'
    process_all_html_files(INPUT_DIR, OUTPUT_CSV, debug_file=DEBUG_FILE)