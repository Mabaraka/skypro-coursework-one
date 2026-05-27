import json
from datetime import datetime

import pandas as pd

from src import views


def test_get_greeting_variants():
    assert views.get_greeting(datetime(2026, 5, 27, 5, 59, 0)) == "Доброй ночи"
    assert views.get_greeting(datetime(2026, 5, 27, 6, 0, 0)) == "Доброе утро"
    assert views.get_greeting(datetime(2026, 5, 27, 13, 0, 0)) == "Добрый день"
    assert views.get_greeting(datetime(2026, 5, 27, 17, 59, 0)) == "Добрый день"
    assert views.get_greeting(datetime(2026, 5, 27, 19, 0, 0)) == "Добрый вечер"
    assert views.get_greeting(datetime(2026, 5, 27, 23, 0, 0)) == "Доброй ночи"


def test_get_month_date_range():
    dt = datetime(2020, 5, 20, 15, 10, 11)
    start, end = views.get_month_date_range(dt)
    assert start == datetime(2020, 5, 1, 0, 0, 0)
    assert end == dt


def test_calculate_card_stats_expected_fields():
    df = pd.DataFrame(
        {
            "date": [datetime(2021, 12, 21), datetime(2021, 12, 20)],
            "card": ["*7197", "1234567890127512"],
            "amount": [1262.0, 7.94],
        }
    )

    result = views.calculate_card_stats(df)
    by_card = {item["last_digits"]: item for item in result}

    assert by_card["7197"]["total_spent"] == 1262.0
    assert by_card["7197"]["cashback"] == 12.62
    assert by_card["7512"]["total_spent"] == 7.94
    assert by_card["7512"]["cashback"] == 0.08


def test_get_top_transactions_with_date_category_and_description():
    df = pd.DataFrame(
        {
            "date": [datetime(2021, 12, 21), datetime(2021, 12, 20), datetime(2021, 12, 16)],
            "amount": [1198.23, 829.00, -14216.42],
            "category": ["Переводы", "Супермаркеты", "ЖКХ"],
            "description": ["Перевод", "Лента", "ЖКУ Квартира"],
        }
    )

    result = views.get_top_transactions(df, limit=2)
    assert len(result) == 2
    assert result[0]["date"] == "21.12.2021"
    assert result[0]["category"] == "Переводы"
    assert result[0]["description"] == "Перевод"
    assert result[1]["amount"] == 829.0


def test_fetch_currency_rates(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"rates": {"USD": 0.01366, "EUR": 0.01148}}

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(views.requests, "get", mock_get)
    result = views.fetch_currency_rates(["USD", "EUR"])

    assert result == [
        {"currency": "USD", "rate": 73.21},
        {"currency": "EUR", "rate": 87.11},
    ]


def test_fetch_stock_prices(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "quoteResponse": {
                    "result": [
                        {"symbol": "AAPL", "regularMarketPrice": 150.12},
                        {"symbol": "AMZN", "regularMarketPrice": 3173.18},
                    ]
                }
            }

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(views.requests, "get", mock_get)
    result = views.fetch_stock_prices(["AAPL", "AMZN"])

    assert result == [
        {"stock": "AAPL", "price": 150.12},
        {"stock": "AMZN", "price": 3173.18},
    ]


def test_build_dashboard_json_full(monkeypatch):
    df = pd.DataFrame(
        {
            "date": [datetime(2021, 12, 21), datetime(2021, 12, 20)],
            "card": ["*5814", "*7512"],
            "amount": [1262.0, 7.94],
            "category": ["Переводы", "Супермаркеты"],
            "description": ["Перевод", "Лента"],
        }
    )

    monkeypatch.setattr(views, "load_operations_dataframe", lambda: df)
    monkeypatch.setattr(
        views,
        "load_user_settings",
        lambda: {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN"]},
    )
    monkeypatch.setattr(
        views,
        "fetch_currency_rates",
        lambda currencies: [{"currency": "USD", "rate": 73.21}, {"currency": "EUR", "rate": 87.08}],
    )
    monkeypatch.setattr(
        views,
        "fetch_stock_prices",
        lambda symbols: [{"stock": "AAPL", "price": 150.12}, {"stock": "AMZN", "price": 3173.18}],
    )

    payload = views.build_dashboard_response("2021-12-21 13:00:00")
    assert payload["greeting"] == "Добрый день"
    assert payload["period"] == {"from": "01.12.2021", "to": "21.12.2021"}
    assert "cards" in payload
    assert "top_transactions" in payload
    assert "expenses" in payload
    assert "income" in payload
    assert isinstance(payload["expenses"]["total"], int)
    assert payload["currency_rates"][0]["currency"] == "USD"
    assert payload["stock_prices"][0]["stock"] == "AAPL"

    json_text = views.build_dashboard_json("2021-12-21 13:00:00")
    parsed = json.loads(json_text)
    assert parsed["greeting"] == "Добрый день"
