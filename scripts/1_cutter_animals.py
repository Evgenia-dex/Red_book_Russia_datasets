import re
from pathlib import Path


def has_cyrillic(text):
    return bool(re.search(r'[а-яёА-ЯЁ]', text))


def sanitize_filename(name):
    # Удаляем html-теги и спецсимволы, чтобы Mac разрешил сохранить файл
    name = re.sub(r'<[^>]+>', '', name)
    name = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    name = re.sub(r'\s+', '_', name)
    return name[:60]  # Ограничиваем длину имени


def extract_species_name(lines):
    # Умный поиск имени: ищем латынь в тегах <i> и берем русское название рядом с ней
    for i, line in enumerate(lines):
        if '<i>' in line and re.search(r'[A-Z][a-z]+', line):
            # Проверяем саму строку с латынью (вдруг русское название на этой же строке)
            clean_line = re.sub(r'<[^>]+>', ' ', line).strip()
            rus_only = re.sub(r'[A-Za-z]+', '', clean_line).strip()

            if has_cyrillic(rus_only) and len(rus_only) > 3:
                return rus_only.strip(' ,.;:-')

            # Если на этой строке только латынь, берем предыдущую строку (там 100% русское название)
            if i > 0:
                prev_clean = re.sub(r'<[^>]+>', ' ', lines[i - 1]).strip()
                if has_cyrillic(prev_clean):
                    return prev_clean.strip(' ,.;:-')

    return "Неизвестный_вид"


def main():
    html_path = Path("your_path")
    out_dir = Path("your_path")

    if not html_path.exists():
        print(f"❌ ОШИБКА: Исходный файл не найден по пути: {html_path}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Читаем исходный файл: {html_path.name}...")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Сохраняем шапку HTML
    header_m = re.search(r'^(.*?<body[^>]*>)', content, re.DOTALL | re.IGNORECASE)
    header = header_m.group(1) if header_m else "<!DOCTYPE html><html><body>"
    footer = "\n</body>\n</html>"

    # Важный шаг: приводим все переносы строк к единому формату <br/>
    normalized_content = re.sub(r'</p>|</div>', '<br/>', content)
    lines = normalized_content.split('<br/>')

    animals = []
    current_chunk = []

    for line in lines:
        current_chunk.append(line)

        # СТРОГИЙ триггер: режем только по авторам-составителям
        if re.search(r'Автор[ы]?[- ]составител[ьяи]', line, re.IGNORECASE):
            animals.append(current_chunk)
            current_chunk = []

    # Сохраняем самый последний кусок книги, если он остался
    if current_chunk and len(current_chunk) > 5:
        animals.append(current_chunk)

    print(f"Успешно разделено на очерки: {len(animals)}")

    for i, chunk in enumerate(animals, 1):
        # Достаем красивое имя вида
        name = extract_species_name(chunk)
        safe_name = sanitize_filename(name)

        filename = f"{i:03d}_{safe_name}.html"

        with open(out_dir / filename, "w", encoding="utf-8") as f:
            f.write(header + "\n")
            f.write("<br/>".join(chunk))
            f.write(footer)

        print(f"  Сохранен: {filename}")

    print(f"\n🚀 ИДЕАЛЬНО! Нарезка завершена. Проверь папку: {out_dir}")


if __name__ == "__main__":
    main()