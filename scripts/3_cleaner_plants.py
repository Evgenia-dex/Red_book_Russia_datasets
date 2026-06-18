import pandas as pd
import re


def clean_author(text):
    if pd.isna(text) or not isinstance(text, str):
        return ''

    # 1. Удаляем все варианты "составителей"
    text = re.sub(r'(?i)(автор[ы]?[- ]составител[ья]|ы[- ]составител[ья]|[- ]составител[ья]|составител[ья])', '', text)

    # 2. Ищем шаблон инициалов
    pattern = r'[А-Я]\.[А-Я]\.\s*[А-Я][а-я]+'
    matches = re.findall(pattern, text)

    if matches:
        return ', '.join(matches)
    return text.strip(' ,.-')


def clean_data(input_file, output_file):
    # Загружаем файл
    df = pd.read_csv(input_file)

    # 1. Склейка переносов (глобальная)
    text_columns = ['distribution', 'habitat', 'abundance', 'limiting_factors',
                    'protection_measures', 'additional_measures', 'author']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'(\w+)-\s+(\w+)', r'\1\2', regex=True)
            df[col] = df[col].replace('nan', '')

    # 2. Очистка страницы: оставляем только первое число
    def get_first_page(text):
        if pd.isna(text): return ''
        # Берем всё до первого символа ';' или пробела, если они есть
        return str(text).split(';')[0].strip()

    if 'page' in df.columns:
        df['page'] = df['page'].apply(get_first_page)

    # 3. Очистка начала ячеек
    df['additional_measures'] = df['additional_measures'].astype(str).str.replace(
        r'^(меры охраны|необходимые дополнительные меры охраны)[.,\s]*', '', flags=re.IGNORECASE, regex=True)
    df['habitat'] = df['habitat'].astype(str).str.replace(
        r'^(и особенности экологии)[.,\s]*', '', flags=re.IGNORECASE, regex=True)

    # 4. Чистка авторов
    df['author'] = df['author'].apply(clean_author)

    # 5. Разделение категории
    def extract_cat_numeric(text):
        m = re.search(r'\b([0-5])\b', str(text))
        return m.group(1) if m else ''

    def extract_cat_text(text):
        codes = re.findall(r'\b(У|III|II|I|КР|НО|НД|БУ|И)\b', str(text))
        return ', '.join(sorted(set(codes)))

    df['category_numeric'] = df['category'].apply(extract_cat_numeric)
    df['category_text'] = df['category'].apply(extract_cat_text)

    # 6. Финальное упорядочивание (точно как в животном датасете)
    # Порядок: latin_name, page, russian_name, family, genus, category_numeric,
    # category_text, distribution, habitat, abundance, limiting_factors,
    # protection_measures, additional_measures, author

    final_columns = [
        'latin_name', 'page', 'russian_name', 'family', 'genus',
        'category_numeric', 'category_text', 'distribution', 'habitat',
        'abundance', 'limiting_factors', 'protection_measures',
        'additional_measures', 'author'
    ]

    # Удаляем старую 'category'
    if 'category' in df.columns:
        df = df.drop(columns=['category'])

    df = df.reindex(columns=final_columns)

    # 7. Сохранение
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"Готово! Файл сохранен в: {output_file}")


if __name__ == "__main__":
    clean_data('/Users/evgeniashemina/Desktop/final_plants/FINAL_CLEAN_DATASET_plants_11.csv',
               '/Users/evgeniashemina/Desktop/final_plants/RED_BOOK_PLANTS_FINAL.csv')