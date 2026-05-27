import json
import logging
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _serialize_report_data(data: Any) -> Any:
    if isinstance(data, pd.DataFrame):
        return json.loads(data.to_json(orient="records", force_ascii=False, date_format="iso"))
    return data


def save_report(filename: Optional[str] = None) -> Callable:
    """
    Декоратор для функций-отчетов.

    - Без параметра: имя файла формируется автоматически
      report_<function_name>_<YYYYmmdd_HHMMSS>.json
    - С параметром: используется переданное имя файла.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            payload = _serialize_report_data(result)

            file_name = (
                filename if filename else f"report_{func.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            path = Path(file_name)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Отчет записан в файл %s", path)
            return result

        return wrapper

    return decorator


@save_report()
def spending_by_category(
    transactions: pd.DataFrame,
    category: str,
    date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Возвращает траты по заданной категории за последние 3 месяца
    относительно переданной даты (или текущей даты, если не передана).
    """
    if transactions.empty:
        return transactions.copy()

    df = transactions.copy()
    date_col = "Дата операции" if "Дата операции" in df.columns else "date"
    amount_col = "Сумма операции" if "Сумма операции" in df.columns else "amount"
    category_col = "Категория" if "Категория" in df.columns else "category"

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df[df[date_col].notna()]

    target_date = pd.to_datetime(date) if date else pd.Timestamp.now()
    start_date = target_date - pd.DateOffset(months=3)

    filtered = df[
        (df[category_col] == category)
        & (df[date_col] >= start_date)
        & (df[date_col] <= target_date)
        & (df[amount_col] > 0)
    ].copy()

    return filtered
