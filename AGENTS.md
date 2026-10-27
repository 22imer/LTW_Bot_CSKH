# AGENTS.md — Telegram CSKH Bot

## Project goal
Build a customer-support Telegram bot for a cafe chain with `python-telegram-bot` v20+ and an LLM agent.

## Current behavior
- `/start` shows two inline shortcuts: store addresses and store contact (no LLM).
- Any text message goes to an LLM agent (OpenAI-compatible API) that can only call 4 tools: `list_stores`, `get_store_contact`, `get_web_link`, `submit_feedback`. The agent persona is "Mây"; shop rules come from `data/faq.md`.
- Context = last 10 messages per user in SQLite (`data/cskh.sqlite3`: `users`, `messages`, `feedback`); history purged after 30 days.
- Telegram command menu (hamburger button): `/start`, `/diachi` (addresses), `/lienhe` (contact picker). Registered at startup by `publish_command_menu`.
- No human agent handoff. Non-text messages get a fixed reply.
- Limits: 10 msgs/min/user, 1000 chars, 3 tool rounds per turn.

## Non-negotiable implementation rules
1. Use async handlers and `await` for Telegram API calls.
2. Read `BOT_TOKEN`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `MENU_URL`, `SHOP_NAME` from environment variables; never commit secrets.
3. Do not use `tel:` in an InlineKeyboardButton URL. Use `send_contact` with an international-format number (`+84...`).
4. Telegram contact messages cannot be edited like text messages. When navigating away from one, delete it if possible and send a new text menu.
5. Keep store data in `data/stores.json`, not scattered throughout handlers.
6. Escape user-provided text before inserting it into HTML-formatted Telegram messages. LLM output is sent as plain text.
7. Handle invalid store IDs, LLM errors and Telegram API errors gracefully.
8. Branch facts reach customers only through tools; do not let the model invent them.
9. Keep changes focused; update `ARCHITECTURE.md` when architecture decisions change.

## Development
- Python 3.10+
- Install: `python -m pip install -r requirements.txt`
- Configure: copy `.env.example` to `.env` and fill it in.
- Run: `python bot.py` or `docker compose up -d --build`
- Test: `python -m unittest discover -s tests -v`

## Backlog
- Human handoff with two-way replies.
- Promotions, table booking, order lookup tools.
- Media message support.
- Webhook deployment and monitoring.
- Per-user locking if updates become concurrent.
