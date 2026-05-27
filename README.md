# SkyPro Coursework One

Проект для формирования JSON-ответов по транзакциям, сервисных функций анализа и отчетов.

## Возможности

- `src/views.py`
  - `build_dashboard_response(datetime_str)` и `build_dashboard_json(datetime_str)`
  - приветствие по времени суток
  - данные по картам (последние цифры, траты, кешбэк)
  - топ-5 транзакций
  - курсы валют и цены акций из `user_settings.json` через `requests`
  - блоки `expenses` и `income` (топ-7 категорий, `other`, `transfers`, `cash`)
- `src/services.py`
  - `analyze_cashback_categories` — топ-3 выгодных категорий кешбэка
  - `investment_bank` — расчет пополнения инвесткопилки с округлением
  - `simple_search` — поиск по подстроке (регистронезависимый)
  - `search_by_phone_numbers` — поиск транзакций с телефонами (regex)
  - `search_person_transfers` — поиск переводов физлицам
- `src/reports.py`
  - декоратор `save_report` (с именем файла и без)
  - отчет `spending_by_category` за последние 3 месяца

## Структура проекта

- `src/` — код приложения
- `tests/` — тесты `pytest`
- `data/operations.xlsx` — входные данные по операциям
- `user_settings.json` — список валют и акций для вывода

## Установка и запуск тестов

```bash
python -m pip install pytest pandas requests openpyxl
python -m pytest
```

## Формат входа для главной функции

`build_dashboard_json(datetime_str)` принимает строку даты и времени:

- `YYYY-MM-DD HH:MM:SS`

Пример:

```python
from src.views import build_dashboard_json

result = build_dashboard_json("2021-12-21 13:00:00")
print(result)
```
