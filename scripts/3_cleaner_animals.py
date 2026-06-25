import pandas as pd
import numpy as np
import re

# Укажи путь к спарсенному файлу (результату работы парсера)
INPUT_CSV = '/Users/evgeniashemina/Desktop/final_animals/parsed_animals_FINAL.csv'
# Укажи путь, куда сохранить финальный чистый датасет
OUTPUT_CSV = '/Users/evgeniashemina/Desktop/final_animals/RED_BOOK_ANIMALS_CLEANED.csv'

# Загружаем CSV
df = pd.read_csv(INPUT_CSV, dtype=str)

# ==========================================
# ХИРУРГИЧЕСКАЯ ОЧИСТКА АРТЕФАКТОВ
# ==========================================
# Убираем "гии." (с точкой и возможным пробелом) ТОЛЬКО в начале строки
if 'habitat' in df.columns:
    df['habitat'] = df['habitat'].str.replace(r'^гии\.\s*', '', regex=True, flags=re.IGNORECASE)

# Убираем "охраны." или "раны." ТОЛЬКО в начале строки
if 'additional_measures' in df.columns:
    df['additional_measures'] = df['additional_measures'].str.replace(r'^(охраны|раны)\.\s*', '', regex=True,
                                                                      flags=re.IGNORECASE)

# На всякий случай прочистим и меры охраны (вдруг там тоже был перенос)
if 'protection_measures' in df.columns:
    df['protection_measures'] = df['protection_measures'].str.replace(r'^(охраны|раны)\.\s*', '', regex=True,
                                                                      flags=re.IGNORECASE)
# ==========================================


# Заменяем пустые строки на NaN для корректной работы pandas
df = df.replace(r'^\s*$', np.nan, regex=True)

# 1. Удаляем полные дубликаты
initial_len = len(df)
df = df.drop_duplicates()
print(f"Удалено полных дубликатов: {initial_len - len(df)}")

# 2. Оставляем только строки, где есть латинское название
df = df.dropna(subset=['latin_name'])


# Умная функция для объединения текстовых полей (склеиваем разорванные страницы)
def merge_text(series):
    series = series.dropna()
    if len(series) == 0:
        return ''
    if len(series) == 1:
        return str(series.iloc[0])

    texts = list(series.astype(str))
    merged_text = texts[0].strip()

    for i in range(1, len(texts)):
        next_text = texts[i].strip()
        if not next_text:
            continue

        # Защита от включения одного куска в другой
        if next_text in merged_text:
            continue
        if merged_text in next_text:
            merged_text = next_text
            continue

        # Если текст с предыдущей страницы обрывается на дефис — склеиваем вплотную
        if merged_text.endswith('-'):
            merged_text = merged_text[:-1] + next_text
        else:
            merged_text += ' ' + next_text

    return merged_text


# 3. Группируем по латинскому названию
grouped = df.groupby('latin_name', as_index=False).agg({
    'page': lambda x: '; '.join(sorted(set(x.astype(str)))),
    'russian_name': 'first',
    'family': 'first',
    'genus': 'first',
    'category_numeric': 'first',
    'category_text': 'first',
    'distribution': merge_text,
    'habitat': merge_text,
    'abundance': merge_text,
    'limiting_factors': merge_text,
    'protection_measures': merge_text,
    'additional_measures': merge_text,
    # Так как авторы теперь идеальны, просто берем первую встретившуюся запись
    'author': 'first'
})

print(f"После группировки по латинскому названию: {len(grouped)} уникальных видов")

# Сохраняем финальный результат
grouped.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
print(f"Сохранено в {OUTPUT_CSV}")