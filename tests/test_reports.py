import json
from pathlib import Path

import pandas as pd

from src.reports import save_report, spending_by_category


def test_save_report_with_custom_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    @save_report("custom_report.json")
    def report_func():
        return {"result": 123}

    result = report_func()
    assert result == {"result": 123}

    file_path = tmp_path / "custom_report.json"
    assert file_path.exists()
    assert json.loads(file_path.read_text(encoding="utf-8")) == {"result": 123}


def test_save_report_with_default_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    @save_report()
    def report_func():
        return [{"a": 1}]

    report_func()
    files = list(Path(tmp_path).glob("report_report_func_*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text(encoding="utf-8")) == [{"a": 1}]


def test_spending_by_category_for_last_three_months(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = pd.DataFrame(
        {
            "Дата операции": ["2024-01-10", "2024-02-15", "2024-03-20", "2023-12-20", "2024-03-25"],
            "Категория": ["Еда", "Еда", "Еда", "Еда", "Транспорт"],
            "Сумма операции": [100.0, 200.0, 300.0, 400.0, 500.0],
        }
    )

    result = spending_by_category(df, "Еда", "2024-03-31")
    assert len(result) == 3
    assert set(result["Сумма операции"].tolist()) == {100.0, 200.0, 300.0}


def test_spending_by_category_ignores_non_expenses(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = pd.DataFrame(
        {
            "Дата операции": ["2024-03-10", "2024-03-11"],
            "Категория": ["Еда", "Еда"],
            "Сумма операции": [120.0, -50.0],
        }
    )

    result = spending_by_category(df, "Еда", "2024-03-31")
    assert len(result) == 1
    assert result.iloc[0]["Сумма операции"] == 120.0
