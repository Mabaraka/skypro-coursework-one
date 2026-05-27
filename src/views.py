import json
import logging
import os
import re
from datetime import datetime, time
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def parse_input_datetime(dt_str: str) -> datetime:
    """
    Преобразует строку формата 'YYYY-MM-DD HH:MM:SS' в объект datetime.
    """
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error("Некорректный формат даты: %s", dt_str)
        raise


def get_greeting(dt: datetime) -> str:
    """
    Возвращает приветствие в зависимости от времени суток.

    Доброе утро  — 06:00–11:59
    Добрый день  — 12:00–17:59
    Добрый вечер — 18:00–22:59
    Доброй ночи  — 23:00–05:59
    """
    current = dt.time()

    if time(6, 0) <= current < time(12, 0):
        return "Доброе утро"
    if time(12, 0) <= current < time(18, 0):
        return "Добрый день"
    if time(18, 0) <= current < time(23, 0):
        return "Добрый вечер"
    return "Доброй ночи"


def get_month_date_range(dt: datetime) -> Tuple[datetime, datetime]:
    """
    Возвращает диапазон дат с начала месяца по входящую дату (включительно).
    Время в начале диапазона сбрасывается к 00:00:00.
    """
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = dt
    return start, end


def _detect_column(df: pd.DataFrame, candidates: List[str]) -> str:
    """
    Находит первый подходящий столбец из списка кандидатов.
    """
    normalized = {col.lower(): col for col in df.columns}
    for cand in candidates:
        low = cand.lower()
        if low in normalized:
            return normalized[low]
    raise KeyError(f"Не удалось найти ни один из столбцов: {candidates}")


def load_operations_dataframe(path: str = os.path.join("data", "operations.xlsx")) -> pd.DataFrame:
    """
    Загружает Excel-файл с операциями в DataFrame.
    """
    logger.info("Загрузка операций из файла %s", path)
    df = pd.read_excel(path)
    if df.empty:
        return df

    # Попытка привести столбец даты к datetime
    try:
        date_col = _detect_column(df, ["date", "Дата операции", "Дата"])
        df[date_col] = pd.to_datetime(df[date_col])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось привести столбец даты к datetime: %s", exc)

    return df


def filter_operations_by_period(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """
    Фильтрует операции по диапазону дат [start; end].
    """
    if df.empty:
        return df

    date_col = _detect_column(df, ["date", "Дата операции", "Дата"])
    mask = (df[date_col] >= start) & (df[date_col] <= end)
    return df.loc[mask].copy()


def calculate_card_stats(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Считает по каждой карте:
    - последние 4 цифры карты;
    - общую сумму расходов;
    - кешбэк (1 рубль на каждые 100 рублей).
    """
    if df.empty:
        return []

    amount_col = _detect_column(df, ["amount", "Сумма операции", "Сумма"])
    card_col = _detect_column(df, ["card", "Номер карты", "Карта"])

    amounts = df[amount_col]
    if (amounts < 0).any():
        expenses = df[amount_col] < 0
        df_exp = df.loc[expenses].copy()
        df_exp["expense_abs"] = df_exp[amount_col].abs()
    else:
        expenses = df[amount_col] > 0
        df_exp = df.loc[expenses].copy()
        df_exp["expense_abs"] = df_exp[amount_col]

    if df_exp.empty:
        return []

    grouped = df_exp.groupby(card_col)["expense_abs"].sum().reset_index()

    card_stats: List[Dict[str, Any]] = []
    for _, row in grouped.iterrows():
        raw_card = str(row[card_col])
        digits_only = "".join(re.findall(r"\d", raw_card))
        source = digits_only if digits_only else raw_card
        last_four = source[-4:] if len(source) >= 4 else source
        total = float(row["expense_abs"])
        cashback = round(total / 100, 2)
        card_stats.append(
            {
                "last_digits": last_four,
                "total_spent": round(total, 2),
                "cashback": cashback,
            }
        )

    return card_stats


def get_top_transactions(df: pd.DataFrame, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Возвращает топ-N транзакций по сумме платежа.
    """
    if df.empty:
        return []

    amount_col = _detect_column(df, ["amount", "Сумма операции", "Сумма"])
    date_col = _detect_column(df, ["date", "Дата операции", "Дата"])
    category_col = None
    description_col = None
    try:
        category_col = _detect_column(df, ["category", "Категория"])
    except KeyError:
        # Категория может отсутствовать — это не критично
        pass
    try:
        description_col = _detect_column(df, ["description", "Описание"])
    except KeyError:
        # Описание может отсутствовать — это не критично
        pass
    df_sorted = df.sort_values(by=amount_col, ascending=False).head(limit)

    top_list: List[Dict[str, Any]] = []
    for _, row in df_sorted.iterrows():
        raw_date = row[date_col]
        if hasattr(raw_date, "strftime"):
            date_text = raw_date.strftime("%d.%m.%Y")
        else:
            date_text = str(raw_date)

        item: Dict[str, Any] = {"date": date_text, "amount": round(float(row[amount_col]), 2)}
        item["category"] = row.get(category_col) if category_col else ""
        item["description"] = row.get(description_col) if description_col else ""
        top_list.append(item)

    return top_list


def _round_to_int(value: float) -> int:
    return int(round(value))


def build_expenses_income_summary(df: pd.DataFrame) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Возвращает сводки расходов и поступлений:
    - top-7 категорий + Остальное;
    - отдельно суммы по переводам и наличным;
    - все суммы округлены до целых.
    """
    if df.empty:
        empty = {"total": 0, "top_categories": [], "other": 0, "transfers": 0, "cash": 0}
        return empty, empty

    amount_col = _detect_column(df, ["amount", "Сумма операции", "Сумма"])
    category_col = _detect_column(df, ["category", "Категория"])

    amounts = df[amount_col]
    has_negative = (amounts < 0).any()
    if has_negative:
        expense_df = df[df[amount_col] < 0].copy()
        expense_df["amount_abs"] = expense_df[amount_col].abs()
        income_df = df[df[amount_col] > 0].copy()
        income_df["amount_abs"] = income_df[amount_col]
    else:
        expense_df = df[df[amount_col] > 0].copy()
        expense_df["amount_abs"] = expense_df[amount_col]
        income_df = df.iloc[0:0].copy()
        income_df["amount_abs"] = 0.0

    def aggregate(block_df: pd.DataFrame) -> Dict[str, Any]:
        if block_df.empty:
            return {"total": 0, "top_categories": [], "other": 0, "transfers": 0, "cash": 0}

        grouped = block_df.groupby(category_col)["amount_abs"].sum().sort_values(ascending=False)
        top7 = grouped.head(7)
        other = grouped.iloc[7:].sum() if len(grouped) > 7 else 0.0

        categories = [{"category": cat, "amount": _round_to_int(float(amount))} for cat, amount in top7.items()]

        transfer_mask = block_df[category_col].astype(str).str.contains("перевод", case=False, na=False)
        cash_mask = block_df[category_col].astype(str).str.contains("налич", case=False, na=False)

        return {
            "total": _round_to_int(float(block_df["amount_abs"].sum())),
            "top_categories": categories,
            "other": _round_to_int(float(other)),
            "transfers": _round_to_int(float(block_df.loc[transfer_mask, "amount_abs"].sum())),
            "cash": _round_to_int(float(block_df.loc[cash_mask, "amount_abs"].sum())),
        }

    return aggregate(expense_df), aggregate(income_df)


def load_user_settings(path: str = "user_settings.json") -> Dict[str, Any]:
    """
    Загружает настройки пользователя из user_settings.json.
    """
    if not os.path.exists(path):
        logger.warning("Файл настроек пользователя %s не найден", path)
        return {"user_currencies": [], "user_stocks": []}

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            logger.error("Не удалось прочитать user_settings.json: %s", exc)
            return {"user_currencies": [], "user_stocks": []}

    return {
        "user_currencies": data.get("user_currencies", []),
        "user_stocks": data.get("user_stocks", []),
    }


def fetch_currency_rates(currencies: List[str]) -> List[Dict[str, Any]]:
    """
    Получает курс валют с использованием внешнего API.
    Возвращает словарь вида {"USD": 93.12, ...} — стоимость 1 единицы валюты в рублях.
    """
    if not currencies:
        return []

    symbols = ",".join(currencies)
    url = "https://api.exchangerate.host/latest"
    params = {"base": "RUB", "symbols": symbols}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.error("Ошибка при запросе курса валют: %s", exc)
        return []

    rates = data.get("rates", {})
    result: List[Dict[str, Any]] = []
    for code in currencies:
        if code in rates:
            # так как base=RUB, rates[code] — это сколько кодов в 1 RUB,
            # поэтому инвертируем, чтобы получить цену 1 единицы валюты в RUB
            try:
                value = float(rates[code])
                if value != 0:
                    result.append({"currency": code, "rate": round(1 / value, 2)})
            except (TypeError, ValueError):
                continue

    return result


def fetch_stock_prices(symbols: List[str]) -> List[Dict[str, Any]]:
    """
    Получает стоимость акций с использованием публичного API Yahoo Finance.
    """
    if not symbols:
        return []

    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    params = {"symbols": ",".join(symbols)}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.error("Ошибка при запросе стоимости акций: %s", exc)
        return []

    quotes = data.get("quoteResponse", {}).get("result", [])
    result: List[Dict[str, Any]] = []
    for quote in quotes:
        symbol = quote.get("symbol")
        price = quote.get("regularMarketPrice")
        if symbol in symbols and price is not None:
            try:
                result.append({"stock": symbol, "price": round(float(price), 2)})
            except (TypeError, ValueError):
                continue

    return result


def build_dashboard_response(datetime_str: str) -> Dict[str, Any]:
    """
    Главная функция: принимает строку с датой/временем
    формата 'YYYY-MM-DD HH:MM:SS' и возвращает словарь,
    готовый к сериализации в JSON.
    """
    dt = parse_input_datetime(datetime_str)
    greeting = get_greeting(dt)
    start, end = get_month_date_range(dt)

    df = load_operations_dataframe()
    df_period = filter_operations_by_period(df, start, end)

    cards = calculate_card_stats(df_period)
    top_transactions = get_top_transactions(df_period, limit=5)
    expenses, income = build_expenses_income_summary(df_period)

    user_settings = load_user_settings()
    currencies = user_settings.get("user_currencies", [])
    stocks = user_settings.get("user_stocks", [])

    currency_rates = fetch_currency_rates(currencies)
    stock_prices = fetch_stock_prices(stocks)

    return {
        "greeting": greeting,
        "period": {
            "from": start.strftime("%d.%m.%Y"),
            "to": end.strftime("%d.%m.%Y"),
        },
        "cards": cards,
        "top_transactions": top_transactions,
        "expenses": expenses,
        "income": income,
        "currency_rates": currency_rates,
        "stock_prices": stock_prices,
    }


def build_dashboard_json(datetime_str: str) -> str:
    """
    Обёртка над build_dashboard_response, возвращающая строку JSON.
    """
    payload = build_dashboard_response(datetime_str)
    return json.dumps(payload, ensure_ascii=False)
