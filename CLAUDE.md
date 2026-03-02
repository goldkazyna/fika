# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fika — Telegram-бот для управления рестораном. Собирает обратную связь от сотрудников (текст/голос), транскрибирует через OpenAI Whisper, анализирует отзывы через GPT-4o, генерирует ежедневные и ежемесячные PDF-отчёты. Интегрирован с Toweco API для получения отзывов клиентов.

## Commands

```bash
# Run bot
poetry run python -m src.bot

# Install dependencies
poetry install

# Lint & format (Ruff, line length 120)
poetry run pre-commit run --all-files

# Docker
docker compose build --pull && docker compose up --detach
docker compose logs -f
```

No unit tests exist in this project.

## Architecture

### Entry Point & Dispatcher

`src/bot/__main__.py` → `src/bot/app.py`. Custom dispatcher (`src/bot/dispatcher.py`) extends aiogram's `Dispatcher` to handle unknown events with a fallback message.

Router inclusion order in `app.py` matters:
1. `commands_router` — /start, /help, /menu
2. `admin_router` — admin dialog (aiogram-dialog)
3. `waiter_router` — staff feedback dialog (aiogram-dialog)

`setup_dialogs(dp)` must be called after all dialog routers are included.

### Aiogram-Dialog Pattern

Dialogs use `StatesGroup` → `Window` → widgets (`Button`, `SwitchTo`, `Select`, `MessageInput`). Each window has a `state`, optional `getter` for data, and widget callbacks. Admin dialog has ~8 windows, waiter dialog has ~4.

### Permission System

`src/bot/filters.py` — `StatusFilter` checks user status: `admin` (from `settings.admins`), `waiter` (exists in DB), `staff` (waiter with assigned role). Usage: `@router.message(StatusFilter("admin"))`.

### Data Layer

SQLite database (`data/sqlite.db`). `WaiterRepository` (`src/bot/waiter_repository.py`) handles all DB operations with raw SQL. Two tables: `waiters` (telegram_id PK, object JSON, deleted, role) and `waiter_reports` (report_id autoincrement, waiter_id, date, message JSON).

### Configuration

`settings.yaml` → Pydantic v2 schema in `src/config_schema.py` → loaded in `src/config.py`. Sensitive values use `SecretStr`. Pre-commit hook auto-generates `settings.schema.yaml` from the Pydantic model when `config_schema.py` changes.

### Report System

`src/bot/daily_report.py` runs two scheduled loops:
- **Daily** at `settings.daily_report_time` (UTC) — fetches 14-day reviews from Toweco, generates AI advice, sends to channel + admins
- **Summary** on 15th and last day of month at 10:00 Almaty time — generates PDF via `src/bot/pdf_report.py` with charts from `src/bot/plotting.py`

Timezone: scheduling in UTC, business logic in `Asia/Almaty`.

### Voice Feedback Flow

1. User sends voice/text in waiter dialog → `add_feedback_handler()` in `src/bot/routers/waiter.py`
2. Voice transcribed via OpenAI Whisper (Russian) in `src/bot/openai_repository.py`
3. Stored in SQLite as JSON, forwarded to Fika channel
4. On startup, pending (untranscribed) voice messages are re-processed

### External APIs

- **Toweco** (`src/bot/toweco_repository.py`): Token auth, auto-reauth on 401, filters out test reviews
- **OpenAI** (`src/bot/openai_repository.py`): Uses HTTP proxy, Whisper for transcription, GPT-4o for analysis/categorization

## Key Conventions

- All handlers are async; background tasks via `asyncio.create_task()`
- FSM storage: Memory (dev) or Redis (prod), configured via `settings.redis_url`
- Ruff for linting/formatting; wildcard imports (F403/F405) are allowed
- Logging configured in `logging.yaml`, colored output via colorlog
- Docker runs as non-root user `poetry` (UID 1500)
