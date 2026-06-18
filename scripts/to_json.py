import pandas as pd
import json


def convert_dataset(csv_path, json_path):
    print(f"Запуск конвертации: {csv_path} -> JSON")

    # Читаем CSV-файл. Обязательно указываем dtype=str,
    # чтобы текстовые коды категорий и номера страниц не искажались
    df = pd.read_csv(csv_path, dtype=str)

    # Заменяем возможные пустые ячейки (NaN) на пустые строки "",
    # чтобы в итоговом JSON не появлялось некорректное значение null
    df = df.fillna('')

    # Сохраняем в JSON массив объектов
    # orient='records' — делает классический формат [{колонка: значение}, {...}]
    # force_ascii=False — КРИТИЧЕСКИ ВАЖНО, чтобы русские буквы оставались русскими, а не превращались в кодировку типа \u0430
    # indent=4 — делает красивую структуру с отступами, которую удобно читать человеку
    df.to_json(json_path, orient='records', force_ascii=False, indent=4)

    print(f"Успешно! Финальный веб-стандарт сохранен в: {json_path}\n")


if __name__ == "__main__":
    # 1. Конвертация датасета по РАСТЕНИЯМ (Флора)
    convert_dataset(
        'your path to csv',
        'your path to json'
    )

    # 2. Конвертация датасета по ЖИВОТНЫМ (Фауна)
    convert_dataset(
        'your path to csv',
        'your path to json'
    )