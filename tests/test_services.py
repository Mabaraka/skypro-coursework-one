import json

import pytest

from src.services import (
    analyze_cashback_categories,
    investment_bank,
    search_by_phone_numbers,
    search_person_transfers,
    simple_search,
)


def test_analyze_cashback_categories_returns_json_map():
    data = [
        {"Дата операции": "2024-05-10", "Сумма операции": 1000, "Категория": "Супермаркеты"},
        {"Дата операции": "2024-05-15", "Сумма операции": 500, "Категория": "Супермаркеты"},
        {"Дата операции": "2024-05-20", "Сумма операции": 2000, "Категория": "Переводы"},
        {"Дата операции": "2024-05-08", "Сумма операции": 700, "Категория": "Транспорт"},
        {"Дата операции": "2024-05-12", "Сумма операции": 50, "Категория": "Кино"},
        {"Дата операции": "2024-04-20", "Сумма операции": 900, "Категория": "Супермаркеты"},
    ]

    result = json.loads(analyze_cashback_categories(data, 2024, 5))
    assert len(result) == 3
    assert result == {"Переводы": 20.0, "Супермаркеты": 15.0, "Транспорт": 7.0}


def test_investment_bank_rounding():
    transactions = [
        {"Дата операции": "2024-05-02", "Сумма операции": 1712.0},
        {"Дата операции": "2024-05-11", "Сумма операции": 149.0},
        {"Дата операции": "2024-04-11", "Сумма операции": 149.0},
        {"Дата операции": "2024-05-12", "Сумма операции": -100.0},
    ]

    # 1712 -> 1750: +38, 149 -> 150: +1
    assert investment_bank("2024-05", transactions, 50) == 39.0


def test_investment_bank_invalid_limit():
    with pytest.raises(ValueError):
        investment_bank("2024-05", [], 30)


def test_simple_search_by_description_and_category():
    transactions = [
        {"Описание": "Оплата в Лента", "Категория": "Супермаркеты"},
        {"Описание": "Такси", "Категория": "Транспорт"},
    ]

    result = json.loads(simple_search("лента", transactions))
    assert len(result) == 1
    assert result[0]["Категория"] == "Супермаркеты"

    result2 = json.loads(simple_search("транспорт", transactions))
    assert len(result2) == 1
    assert result2[0]["Описание"] == "Такси"


def test_search_by_phone_numbers():
    transactions = [
        {"Описание": "Я МТС +7 921 11-22-33", "Категория": "Связь"},
        {"Описание": "Тинькофф Мобайл +7 995 555-55-55", "Категория": "Связь"},
        {"Описание": "МТС Mobile +7 (981) 333-44-55", "Категория": "Связь"},
        {"Описание": "Оплата 89000000000", "Категория": "Связь"},
        {"Описание": "Кофейня", "Категория": "Рестораны"},
    ]

    result = json.loads(search_by_phone_numbers(transactions))
    assert len(result) == 4


def test_search_person_transfers():
    transactions = [
        {"Описание": "Валерий А.", "Категория": "Переводы"},
        {"Описание": "Сергей З.", "Категория": "Переводы"},
        {"Описание": "Перевод юрлицу ООО Ромашка", "Категория": "Переводы"},
        {"Описание": "Артем П.", "Категория": "Супермаркеты"},
    ]

    result = json.loads(search_person_transfers(transactions))
    assert len(result) == 2
    assert all(item["Категория"] == "Переводы" for item in result)
