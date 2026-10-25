# URL Shortener API

REST API, который сокращает ссылки, редиректит по короткому коду и считает переходы.

## Эндпоинты

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/api/links` | создать короткую ссылку |
| GET | `/api/links` | список ссылок (`limit`, `offset`) |
| GET | `/api/links/{code}` | информация и число кликов |
| DELETE | `/api/links/{code}` | удалить ссылку |
| GET | `/{code}` | редирект на исходный URL (307) |
| GET | `/health` | проверка живости |

Пример:

```bash
curl -X POST http://localhost:8000/api/links \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "code": "promo"}'
```

Ответ:

```json
{
  "code": "promo",
  "original_url": "https://example.com",
  "short_url": "http://localhost:8000/promo",
  "clicks": 0,
  "created_at": "2026-10-25T18:00:00Z"
}
```

Документация Swagger — http://localhost:8000/docs

## Стек

- Python 3.12+
- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async), SQLite по умолчанию, PostgreSQL в Docker
- pytest + httpx

## Запуск локально

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Запуск в Docker

```bash
docker compose up --build
```

Поднимается API на `localhost:8000` и PostgreSQL. Строка подключения задаётся
переменной `DATABASE_URL`, по умолчанию используется SQLite-файл `links.db`.

## Тесты

```bash
pytest -q
```

## Структура

```
app/main.py     эндпоинты, lifespan, редирект
app/models.py   модель Link
app/schemas.py  схемы запросов и ответов
app/db.py       движок SQLAlchemy и сессия
tests/test_api.py
```
