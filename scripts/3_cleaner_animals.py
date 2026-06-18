import pandas as pd
import re


def clean_animals_dataset(input_path, output_path):
    print("Запуск очистки датасета с животными...")

    try:
        # 1. Загрузка сырого датасета
        df = pd.read_csv(input_path)
        initial_rows = len(df)

        # Очищаем названия колонок от случайных пробелов
        df.columns = df.columns.str.strip()

        # 2. Удаление строк, где нет критически важных данных (названия или категории)
        df = df.dropna(subset=['Русское название', 'Латинское название', 'Категория редкости'])

        # 3. Очистка текстовых полей от лишних пробелов по краям
        text_columns = ['Русское название', 'Латинское название', 'Категория редкости', 'Авторы']
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        # 4. Нормализация категорий редкости (приводим к единому стандарту, например "3", "1A" и т.д.)
        # Удаляем точки, лишние знаки и приводим к верхнему регистру
        df['Категория редкости'] = df['Категория редкости'].apply(lambda x: re.sub(r'[\s\.]', '', x).upper())

        # 5. Очистка колонки "Авторы" от квадратных скобок, лишних знаков и опечаток склейки
        if 'Авторы' in df.columns:
            def clean_authors(text):
                if pd.isna(text) or text.lower() == 'nan':
                    return "Не указан"
                # Удаляем квадратные и круглые скобки вместе с содержимым (часто там технические пометки)
                text = re.sub(r'\[.*?\]', '', text)
                text = re.sub(r'\(.*?\)', '', text)
                # Заменяем множественные пробелы на один
                text = re.sub(r'\s+', ' ', text)
                return text.strip()

            df['Авторы'] = df['Авторы'].apply(clean_authors)

        # 6. Сохранение финального валидированного продукта
        df.to_csv(output_path, index=False, encoding='utf-8')

        final_rows = len(df)
        print(f"Очистка успешно завершена!")
        print(
            f"Было строк: {initial_rows} -> Стало строк: {final_rows} (Удалено пустых/корректных: {initial_rows - final_rows})")
        print(f"Файл сохранен по пути: {output_path}")

    except FileNotFoundError:
        print(f"Ошибка: Не удалось найти исходный файл по пути {input_path}")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")


if __name__ == "__main__":
    # Указываем пути в соответствии с вашим запросом
    INPUT_FILE = "your_path/raw_animals_dataset.csv"
    OUTPUT_FILE = "your_path/final_animals_dataset.csv"

    clean_animals_dataset(INPUT_FILE, OUTPUT_FILE)