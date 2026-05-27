import json
import logging
import math
import re
from datetime import datetime
from functools import reduce
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _get_field(transaction: Dict[str, Any], field_names: List[str], default: Any = None) -> Any:
    return (
        reduce(
            lambda acc, key: transaction[key] if acc is None and key in transaction else acc,
            field_names,
            None,
        )
        or default
    )


def _parse_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    raise ValueError(f"Невалидная дата операции: {value}")


def _to_transactions(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    # Поддержка pandas.DataFrame без жесткой зависимости от pandas в модуле services.
    if hasattr(data, "to_dict"):
        return data.to_dict(orient="records")
    raise TypeError("Ожидается список транзакций или DataFrame")


def analyze_cashback_categories(data: Any, year: int, month: int) -> str:
    """
    Возвращает JSON с потенциальным кешбэком по категориям за указанный месяц.
    Кешбэк рассчитывается как 1% от суммы трат по категории.
    """
    transactions = _to_transactions(data)

    def in_target_month(transaction: Dict[str, Any]) -> bool:
        raw_date = _get_field(transaction, ["Дата операции", "date", "Дата"])
        try:
            dt = _parse_date(raw_date)
            return dt.year == year and dt.month == month
        except ValueError:
            return False

    def extract_expense(transaction: Dict[str, Any]) -> Dict[str, float]:
        category = _get_field(transaction, ["Категория", "category"], "Без категории")
        amount = float(_get_field(transaction, ["Сумма операции", "amount", "Сумма"], 0.0))
        expense = abs(amount) if amount < 0 else amount
        return {"category": category, "expense": expense}

    month_transactions = list(filter(in_target_month, transactions))
    expenses = list(map(extract_expense, month_transactions))

    grouped = reduce(
        lambda acc, item: {**acc, item["category"]: acc.get(item["category"], 0.0) + item["expense"] * 0.01},
        expenses,
        {},
    )

    sorted_items = sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    top_items = sorted_items[:3] if len(sorted_items) >= 3 else sorted_items
    normalized = {category: round(value, 2) for category, value in top_items}
    logger.info("Рассчитан кешбэк по %s категориям", len(normalized))
    return json.dumps(normalized, ensure_ascii=False)


def investment_bank(month: str, transactions: List[Dict[str, Any]], limit: int) -> float:
    """
    Считает сумму, которую можно было отложить в «Инвесткопилку» за месяц.
    month: 'YYYY-MM'
    """
    if limit not in {10, 50, 100}:
        raise ValueError("Параметр limit должен быть одним из значений: 10, 50, 100")

    try:
        target_year, target_month = map(int, month.split("-"))
    except ValueError as exc:
        raise ValueError("Параметр month должен быть в формате YYYY-MM") from exc

    def eligible(transaction: Dict[str, Any]) -> bool:
        raw_date = _get_field(transaction, ["Дата операции", "date", "Дата"])
        amount = float(_get_field(transaction, ["Сумма операции", "amount", "Сумма"], 0.0))
        if amount <= 0:
            return False
        try:
            dt = _parse_date(raw_date)
            return dt.year == target_year and dt.month == target_month
        except ValueError:
            return False

    def top_up(transaction: Dict[str, Any]) -> float:
        amount = float(_get_field(transaction, ["Сумма операции", "amount", "Сумма"], 0.0))
        rounded = math.ceil(amount / limit) * limit
        return rounded - amount

    total = reduce(lambda acc, txn: acc + top_up(txn), filter(eligible, transactions), 0.0)
    result = round(total, 2)
    logger.info("Сумма для инвесткопилки за %s: %s", month, result)
    return result


def simple_search(query: str, transactions: List[Dict[str, Any]]) -> str:
    """
    Возвращает JSON со всеми транзакциями, где запрос найден в описании или категории.
    """
    q = query.lower().strip()

    def matches(transaction: Dict[str, Any]) -> bool:
        description = str(_get_field(transaction, ["Описание", "description"], "")).lower()
        category = str(_get_field(transaction, ["Категория", "category"], "")).lower()
        return q in description or q in category

    result = list(filter(matches, transactions))
    logger.info("По запросу '%s' найдено %s транзакций", query, len(result))
    return json.dumps(result, ensure_ascii=False)


def search_by_phone_numbers(transactions: List[Dict[str, Any]]) -> str:
    """
    Возвращает JSON со всеми транзакциями, содержащими мобильные номера РФ.
    """
    phone_pattern = re.compile(r"(?:\+7|8)\D*\d{3}\D*(?:\d{3}\D*\d{2}\D*\d{2}|\d{2}\D*\d{2}\D*\d{2})")

    def has_phone(transaction: Dict[str, Any]) -> bool:
        description = str(_get_field(transaction, ["Описание", "description"], ""))
        return bool(phone_pattern.search(description))

    result = list(filter(has_phone, transactions))
    logger.info("Найдено %s транзакций с номерами телефонов", len(result))
    return json.dumps(result, ensure_ascii=False)


def search_person_transfers(transactions: List[Dict[str, Any]]) -> str:
    """
    Возвращает JSON со всеми переводами физлицам:
    - категория 'Переводы'
    - описание содержит 'Имя Ф.'
    """
    person_pattern = re.compile(r"\b[А-ЯЁ][а-яё]+\s[А-ЯЁ]\.")

    def is_person_transfer(transaction: Dict[str, Any]) -> bool:
        category = str(_get_field(transaction, ["Категория", "category"], ""))
        description = str(_get_field(transaction, ["Описание", "description"], ""))
        return category == "Переводы" and bool(person_pattern.search(description))

    result = list(filter(is_person_transfer, transactions))
    logger.info("Найдено %s переводов физлицам", len(result))
    return json.dumps(result, ensure_ascii=False)
