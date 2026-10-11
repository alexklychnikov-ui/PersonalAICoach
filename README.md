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
| **Рынок** | Поиск **hh.ru** / **Kwork**, ручной импорт текста вакансии/ТЗ, **skill-gap** (gaps / strengths / score) |
| **Коучинг** | Диалог в контексте трека; опционально KB → пометка `[KB]`; weekly check-in (mood / wins / blockers) |
| **Mock interview** | Вопросы под роль → ответы → structured feedback |
| **Telegram** | `/start` `/status` `/checkin`, check-in вида `4 \| wins \| blockers`, свободный текст → coaching turn |
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
                         ├── hh / Kwork / manual (MarketSourcePort)
                         └── LightRAG MCP / DisabledKB (KnowledgeBasePort)
```

Паттерн: тонкие клиенты (UI/bot) → один API. Рынок и skill-gap работают без RAG; KB — feature flag.

**Стек:** Python 3.12 · FastAPI · MongoDB · Streamlit · aiogram 3 · OpenAI · Docker Compose · Caddy (prod TLS).

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
3. **Рынок / Skill-gap** → `manual` / `hh` / `kwork` → анализ.
4. **Коучинг** / **Интервью** — неделя и подготовка к собесу.
5. Telegram — быстрый check-in и короткие вопросы.

---

## Переменные окружения

Шаблон: [`env.example`](env.example) → копируй в `.env` (в git не коммитится).

| Переменная | Смысл |
|---|---|
| `OPENAI_API_KEY` | LLM; пусто → StubLLM |
| `MONGO_*` / `MONGO_URI` | MongoDB |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_OWNER_ID` | Бот только для владельца |
| `TELEGRAM_USE_WEBHOOK` | `false` = polling (по умолчанию) |
| `KNOWLEDGE_BASE_ENABLED` | RAG on/off |
| `MCP_LIGHTRAG_*` / `LIGHTRAG_*` | Подключение к LightRAG при `ENABLED=true` |
| `HH_*` | Поиск вакансий (приложение на [dev.hh.ru](https://dev.hh.ru); см. `scripts/hh_get_token.py`) |
| `KWORK_*` | Read-only рынок Kwork |
| `PUBLIC_BASE_URL` | Публичный URL (prod / webhook) |

---

## Структура репозитория

```
app/                 # FastAPI: routers, services, domain, ports, adapters, worker
bot/                 # aiogram polling → internal API
frontend/            # Streamlit dashboard
scripts/             # deploy_vps.ps1, smoke_test, hh_get_token, tg_ping
tests/
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

**Ближайшее**

- Живой hh после модерации приложения и app-token
- Rate limit на LLM-эндпоинты, `ai_audit_log`, бэкап Mongo
- Telegram webhook mode на домене коуча
- Disclaimer / Basic Auth на UI для single-user

**Дальше по продукту**

- Адаптеры FL.ru / Habr Career / ATS (Greenhouse и т.п.)
- Голос (STT/TTS) в mock interview
- Загрузка документов в LightRAG из UI коуча
- Более жёсткий weekly ritual: дайджест прогресса + авто-задачи из skill-gap

**Масштаб (если выйдет за личный MVP)**

- Multi-user + auth, шифрование чувствительных полей at-rest
- Telegram Mini App
- Оркестрация сложных сценариев (LangGraph / агенты) — только там, где single-call LLM уже не тянет

**Сознательно не в scope MVP:** автоотклики на hh/Kwork, Selenium как основной путь, публичный SaaS с OAuth.

---

## Лицензия и дисклеймер

Личный / портфолио-проект. Данные и ключи — ответственность владельца инстанса; не коммить `.env`. Не является юридической или кадровой консультацией.
