# Personal AI Coach

AI-коуч для карьеры: онбординг, план, skill-gap (hh/Kwork/manual), weekly coaching, mock interview, Telegram check-in, опциональный LightRAG.

**Prod:** https://aicareercoach.alexklyvibe.ru/ · VPS `193.168.196.12` · SSH `AIcareerСoach`

## Стек

Python 3.12 · FastAPI · MongoDB · Streamlit · aiogram 3 · OpenAI · Docker Compose

## Быстрый старт (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy env.example .env   # если ещё нет; заполни секреты
# Mongo локально или:
docker compose up -d mongo
# в .env: MONGO_HOST=127.0.0.1, MONGO_PASSWORD как в compose

uvicorn app.main:app --reload --port 8000
# другой терминал:
streamlit run frontend/app.py
# опционально:
python -m bot.main
python -m app.worker
```

Health: http://127.0.0.1:8000/health  
UI: http://127.0.0.1:8501  
API docs: http://127.0.0.1:8000/docs

Полный стек:

```powershell
docker compose up -d --build
```

## Переменные

См. `env.example`. Важно:

| Переменная | Смысл |
|---|---|
| `OPENAI_API_KEY` | LLM (без ключа — StubLLM для smoke) |
| `MONGO_*` | MongoDB |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_OWNER_ID` | бот только для владельца |
| `KNOWLEDGE_BASE_ENABLED` | `false` = без LightRAG |
| `HH_*` / `KWORK_*` | рынок труда |

## Тесты

```powershell
pytest -q
```

## Структура

```
app/          # FastAPI, сервисы, адаптеры
bot/          # aiogram polling
frontend/     # Streamlit
tests/
docker-compose.yml
env.example
Docs/todoList.md
```

## Deploy (VPS)

```powershell
ssh AIcareerСoach
# снести старый AI-PredictiveSalesAnalytics при необходимости
# /opt/personal-ai-coach + docker compose
```

Подробный план: [Docs/todoList.md](Docs/todoList.md).
