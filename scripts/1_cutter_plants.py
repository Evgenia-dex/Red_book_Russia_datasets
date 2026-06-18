import re
from pathlib import Path


def get_top(tag_str):
    m = re.search(r'top:(\d+)px', tag_str)
    return int(m.group(1)) if m else 0


def get_left(tag_str):
    m = re.search(r'left:(\d+)px', tag_str)
    return int(m.group(1)) if m else 0


def is_new_plant_anchor(stream, idx):
    """
    Умный детектор нового растения.
    """
    p = stream[idx]
    text = p['text']
    raw_html = p['str']  # Берем сырой HTML тега, чтобы проверить жирность

    # 1. Просеиваем очевидный мусор (длинные абзацы)
    if len(text.split()) > 15 or len(text) > 150:
        return False

    # 2. Должно начинаться с большой русской буквы (или скобки)
    if not re.match(r'^[\(\[]?[А-ЯЁ]', text):
        return False

    # 3. ЗАЩИТА: Названия растений не содержат цифр!
    # Это убьет все случайные фразы типа "Приморского..., 2022)"
    if re.search(r'\d', text):
        return False

    # 4. ЗАЩИТА: Название растения ОБЯЗАТЕЛЬНО выделено жирным шрифтом
    # Это моментально отсеет любой обычный текст
    if '<b>' not in raw_html:
        return False

    # 5. Исключаем ошибочные заголовки разделов
    forbidden = ['Категория', 'Краткая', 'Распространение', 'Места', 'Численность', 'Лимитирующие', 'Принятые',
                 'Необходимые', 'Автор']
    if any(text.startswith(fw) for fw in forbidden):
        return False

    # 6. ИЩЕМ АЛИБИ: "Латынь" и "Семейство" в следующих 5-ти строках
    end_idx = min(idx + 6, len(stream))
    has_latin = False
    has_family = False

    for j in range(idx + 1, end_idx):
        neighbor = stream[j]
        neighbor_text = neighbor['text']

        # Если строка "улетела" в другую колонку или слишком далеко вниз - прерываем поиск
        if abs(neighbor['left'] - p['left']) > 200 or (neighbor['top'] - p['top']) > 200:
            continue

        if re.search(r'[a-zA-Z]', neighbor_text):
            has_latin = True

        if neighbor_text.startswith('Семейство'):
            has_family = True

    return has_latin and has_family

    # 2. ИЩЕМ АЛИБИ: "Латынь" и "Семейство" в следующих 4-х строках
    end_idx = min(idx + 5, len(stream))
    has_latin = False
    has_family = False

    for j in range(idx + 1, end_idx):
        neighbor = stream[j]
        neighbor_text = neighbor['text']

        # Если строка "улетела" в другую колонку или слишком далеко вниз - прерываем поиск
        if abs(neighbor['left'] - p['left']) > 200 or (neighbor['top'] - p['top']) > 160:
            continue

        if re.search(r'[a-zA-Z]', neighbor_text):
            has_latin = True

        if neighbor_text.startswith('Семейство'):
            has_family = True

    return has_latin and has_family


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    name = re.sub(r'\s+', '_', name)
    return name[:80]  # Ограничиваем длину имени файла


def extract_page_parts(block):
    p_pattern = re.compile(r'<p\b[^>]*>.*?</p>', re.DOTALL)
    p_matches = list(p_pattern.finditer(block))

    if not p_matches:
        return block, [], ''

    preamble = block[:p_matches[0].start()]
    tail = block[p_matches[-1].end():]

    p_tags = []
    for m in p_matches:
        tag_str = m.group()
        text = re.sub(r'<[^>]+>', '', tag_str)
        text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text).strip()

        p_tags.append({
            'str': tag_str,
            'top': get_top(tag_str),
            'left': get_left(tag_str),
            'text': text
        })

    return preamble, p_tags, tail


def build_html(preamble, p_elements, tail):
    if not p_elements:
        return ""
    p_strs = [p['str'] for p in p_elements]
    return preamble + '\n' + '\n'.join(p_strs) + '\n' + tail


def main():
    html_path = Path("/Users/evgeniashemina/Desktop/final_plants/kk_plants_cut_classes-html.html")
    out_dir = Path("/Users/evgeniashemina/Desktop/final_plants/splited_plants_final")
    out_dir.mkdir(exist_ok=True)

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    header_m = re.search(r'^(.*?<body[^>]*>)', content, re.DOTALL)
    if not header_m:
        raise ValueError("Не найден тег <body>")
    header = header_m.group(1)
    footer = "\n</body>\n</html>"

    page_blocks_raw = re.split(r'(<div id="page\d+-div".*?>)', content, flags=re.DOTALL)
    page_blocks = []
    for i in range(1, len(page_blocks_raw), 2):
        div_start = page_blocks_raw[i]
        div_content = page_blocks_raw[i + 1] if i + 1 < len(page_blocks_raw) else ''
        page_blocks.append(div_start + div_content)

    print(f"Найдено страниц: {len(page_blocks)}")

    plants = []
    current_plant = None

    for block in page_blocks:
        preamble, p_elements, tail = extract_page_parts(block)
        if not p_elements:
            continue

        col0 = [p for p in p_elements if p['left'] < 430]
        col1 = [p for p in p_elements if p['left'] >= 430]
        col0.sort(key=lambda x: x['top'])
        col1.sort(key=lambda x: x['top'])
        logical_stream = col0 + col1

        current_chunk_elements = []

        for idx, p in enumerate(logical_stream):
            if is_new_plant_anchor(logical_stream, idx):
                if current_plant and current_chunk_elements:
                    chunk_html = build_html(preamble, current_chunk_elements, tail)
                    current_plant["chunks"].append(chunk_html)

                current_plant = {
                    "name": sanitize_filename(p['text']),
                    "chunks": []
                }
                plants.append(current_plant)
                current_chunk_elements = []

            current_chunk_elements.append(p)

        if current_plant and current_chunk_elements:
            chunk_html = build_html(preamble, current_chunk_elements, tail)
            current_plant["chunks"].append(chunk_html)

    print(f"Успешно распознано растений: {len(plants)}")

    for i, plant in enumerate(plants, 1):
        filename = f"{i:03d}_{plant['name']}.html"
        with open(out_dir / filename, "w", encoding="utf-8") as f:
            f.write(header + "\n")
            f.write("".join(plant["chunks"]))
            f.write(footer)

    print(f"\nГотово! Файлы лежат в {out_dir}/")


if __name__ == "__main__":
    main()