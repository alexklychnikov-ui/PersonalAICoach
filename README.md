# Personal AI Coach

Личный AI-коуч для карьеры: один активный трек-цель, структурированный план, skill-gap по рынку, weekly coaching, mock interview и Telegram check-in. Опционально обогащает ответы контекстом из LightRAG (MCP), без жёсткой зависимости от RAG.

| | |
|---|---|
| **Demo** | https://aicareercoach.alexklyvibe.ru/ |
| **Telegram** | [@alexvibeaipersonalcoach_bot](https://t.me/alexvibeaipersonalcoach_bot) |
| **API docs** | `/docs` на API-сервисе |

> Single-user MVP: без регистрации и multi-tenant. Бот отвечает только `TELEGRAM_OWNER_ID`.

---

## Зачем это

Карьерный фокус легко размазывается между «учусь», «откликаюсь» и «жду оффер». Коуч держит **одну активную цель**, генерит план с задачами, сверяет профиль с вакансией/заказом и принимает короткий weekly check-in — в UI или в Telegram.

Типовые цели (треки):

- устройство на работу (`employment`)
- доп. заработок (`side_income`)
- первый фриланс-заказ (`first_freelance_order`)
- своя формулировка (`custom`)

Несколько треков можно хранить; активен только один.

---

## Что умеет сейчас

| Блок | Возможности |
|---|---|
| **Онбординг** | Профиль (роль, навыки, зоны роста, часы/нед), upsert трека, переключение активного, seed из LightRAG-профиля |
| **План** | AI-план (горизонты, навыки, ресурсы), чек-лист задач, Done, % прогресса |
| **Рынок** | **hh.ru** / **Kwork** / **FL.ru** / **Яндекс.Услуги** / **Telegram-каналы** (редактируемый список) / manual → **skill-gap** (RU UI) |
| **Коучинг** | Диалог в контексте трека; опционально KB → пометка `[KB]`; weekly check-in (mood / wins / blockers) |
| **Mock interview** | Вопросы под роль → ответы с автосохранением черновика → structured feedback |
| **Telegram bot** | Кнопочное меню: статус / прогресс / check-in-воронка / спросить коуча (`/start` открывает меню) |
| **Worker** | Напоминания / poll рынка (отдельный процесс) |

Без `OPENAI_API_KEY` поднимается **StubLLM** (smoke/демо).  
`KNOWLEDGE_BASE_ENABLED=false` — коучинг без RAG; при `true` и падении MCP — degraded mode, без 500.

---

## Архитектура

```
Streamlit UI ──┐
Telegram bot ──┼──► FastAPI (routers → services → ports/adapters) ──► MongoDB
Worker ────────┘         │
                         ├── OpenAI (LLMPort)
                         ├── hh / Kwork / FL.ru / Яндекс.Услуги / Telegram (t.me/s + optional Telethon) / manual
                         └── LightRAG MCP / DisabledKB (KnowledgeBasePort)
```

Паттерн: тонкие клиенты (UI/bot) → один API. Рынок и skill-gap работают без RAG; KB — feature flag.

**Стек:** Python 3.12 · FastAPI · MongoDB · Streamlit · aiogram 3 · Telethon (опц.) · Playwright · OpenAI · Docker Compose · Caddy (prod TLS).

---

## Быстрый старт (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy env.example .env
# заполни MONGO_*, OPENAI_API_KEY (опционально), TELEGRAM_* при необходимости

docker compose up -d mongo
# в .env: MONGO_HOST=127.0.0.1, пароль как в compose

uvicorn app.main:app --reload --port 8000
# другой терминал:
streamlit run frontend/app.py
# опционально:
python -m bot.main
python -m app.worker
```

| URL | Назначение |
|---|---|
| http://127.0.0.1:8000/health | Health |
| http://127.0.0.1:8000/docs | OpenAPI |
| http://127.0.0.1:8501 | Streamlit UI |

Полный стек одной командой:

```powershell
docker compose up -d --build
```

Smoke (локально/против API):

```powershell
pytest -q
python scripts/smoke_test.py
```

### Типовой сценарий в UI

1. **Онбординг** → сохранить профиль и трек (или «Заполнить из LightRAG-профиля»).
2. **План** → «Сгенерировать план» → отмечать задачи Done.
3. **Рынок / Skill-gap** → `hh` / `kwork` / `flru` / `yandex_uslugi` / `telegram` / `manual` → анализ.
4. **Коучинг** / **Интервью** — неделя и подготовка к собесу.
5. Telegram-бот — кнопки: статус / прогресс / check-in-воронка / спросить коуча.

**Telegram-каналы (рынок):** в UI сохрани список `@channel` / `t.me/…` → **Искать** фильтрует по всем каналам; в карточке префикс `[@channel]`. Публичные — через `t.me/s/…`; глубже/приват — `python scripts/telegram_login.py --list` + `TELEGRAM_API_*` / `secrets/telegram.session.txt`.

---

## Переменные окружения

Шаблон: [`env.example`](env.example) → копируй в `.env` (в git не коммитится).

| Переменная | Смысл |
|---|---|
| `OPENAI_API_KEY` | LLM; пусто → StubLLM |
| `MONGO_*` / `MONGO_URI` | MongoDB |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_OWNER_ID` | Бот только для владельца |
| `TELEGRAM_USE_WEBHOOK` | `false` = polling (по умолчанию) |
| `TELEGRAM_MARKET_ENABLED` / `TELEGRAM_CHANNELS` | Рынок по TG-каналам; дефолтный seed списка |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` / `TELEGRAM_SESSION*` | Опциональный Telethon (приват + больше истории) |
| `TELEGRAM_HISTORY_LIMIT` | Сколько сообщений тянуть на канал через Telethon |
| `KNOWLEDGE_BASE_ENABLED` | RAG on/off |
| `MCP_LIGHTRAG_*` / `LIGHTRAG_*` | Подключение к LightRAG при `ENABLED=true` |
| `HH_*` | Поиск вакансий ([dev.hh.ru](https://dev.hh.ru); `scripts/hh_get_token.py`). Без токена API честно отдаёт 503 |
| `KWORK_*` | Read-only Kwork (keyword + `KWORK_CATEGORY_IDS`; опц. `KWORK_STORAGE_STATE`) |
| `FLRU_*` | FL.ru: `FLRU_STORAGE_STATE` = Playwright cookies |
| `YANDEX_*` | Яндекс.Услуги: `YANDEX_STORAGE_STATE` + listing `cab/orders` |
| `PUBLIC_BASE_URL` | Публичный URL (prod / webhook) |

FL.ru и Яндекс.Услуги без актуальных cookies вернут пустой список. Сессии логинятся интерактивно в репо **Freelance Auto-Responder** (`deploy/*_login_interactive.py` → `data/*_storage.json`), путь к JSON кладётся в `.env` коуча. На VPS файлы кладутся в `secrets/` и монтируются в контейнеры.

---

## Структура репозитория

```
app/                 # FastAPI: routers, services, domain, ports, adapters, worker
bot/                 # aiogram polling → internal API
frontend/            # Streamlit dashboard
scripts/             # deploy_vps, smoke, hh_get_token, telegram_login, live checks
tests/
secrets/             # local/VPS: storage JSON + telegram.session.txt (gitignored)
docker-compose.yml   # local
compose.prod.yaml    # VPS: api, worker, bot, streamlit, mongo, caddy
Caddyfile
env.example
```

---

## Deploy (VPS)

Целевой хост: `193.168.196.12`, домен `aicareercoach.alexklyvibe.ru`, SSH Host `AIcareerСoach` (в `~/.ssh/config` — кириллическая «С»).

```powershell
# с машины разработки:
.\scripts\deploy_vps.ps1
# или вручную на сервере:
ssh AIcareerСoach
# /opt/personal-ai-coach + docker compose -f compose.prod.yaml up -d --build
```

Prod-сервисы: Caddy (HTTPS) → Streamlit + API; отдельно worker, bot, Mongo (только внутренняя docker-сеть).

---

## Roadmap / перспектива

**Сделано недавно**

- Редактируемый список Telegram-каналов + поиск по всем с пометкой канала
- Kwork keyword/categories; FL.ru / Яндекс.Услуги adapters; skill-gap RU UI
- HH: явная ошибка без токена / на 403; interview draft autosave
- Telegram-бот: кнопочное меню и check-in воронкой (без `4|wins|blockers`)

**Ближайшее**

- Живой hh после модерации приложения и app-token
- Telethon-сессия на VPS для приватных TG-каналов (если нужна глубина)
- Rate limit на LLM-эндпоинты, `ai_audit_log`, бэкап Mongo
- Telegram webhook mode на домене коуча
- Disclaimer / Basic Auth на UI для single-user

**Дальше по продукту**

- Habr Career / ATS; устойчивый Playwright-пул для FL/Яндекс
- Голос (STT/TTS) в mock interview
- Загрузка документов в LightRAG из UI коуча
- Weekly ritual: дайджест прогресса + авто-задачи из skill-gap

**Масштаб (если выйдет за личный MVP)**

- Multi-user + auth, шифрование чувствительных полей at-rest
- Telegram Mini App
- Оркестрация сложных сценариев (LangGraph / агенты) — только там, где single-call LLM уже не тянет

**Сознательно не в scope MVP:** автоотклики на hh/Kwork, Selenium как основной путь, публичный SaaS с OAuth.

---

## Лицензия и дисклеймер

Личный / портфолио-проект. Данные и ключи — ответственность владельца инстанса; не коммить `.env`. Не является юридической или кадровой консультацией.
