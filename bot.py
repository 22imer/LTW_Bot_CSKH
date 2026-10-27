"""Telegram CSKH bot entry point."""
from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application

from cskh.agent import build_system_prompt
from cskh.config import Settings
from cskh.db import Database
from cskh.handlers import DEPS_KEY, Deps, publish_command_menu, register_handlers
from cskh.ratelimit import RateLimiter
from cskh.stores import load_stores

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 24 * 3600
PURGE_TASK_KEY = "purge_task"


async def _purge_loop(db: Database, days: int) -> None:
    while True:
        try:
            removed = await db.purge_messages_older_than(days)
            logger.info("Purged %d messages older than %d days", removed, days)
        except Exception:
            logger.exception("History purge failed")
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)


def build_application(settings: Settings) -> Application:
    settings.validate()
    stores = load_stores(settings.stores_file)
    texts: dict[str, str] = {}
    for label, path in (("FAQ", settings.faq_file), ("menu", settings.menu_file)):
        try:
            texts[label] = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Cannot read {label} file {path}: {exc}") from exc
    db = Database(settings.db_path)
    deps = Deps(
        settings=settings,
        stores=stores,
        db=db,
        limiter=RateLimiter(settings.rate_limit_messages, settings.rate_limit_window_seconds),
        llm=AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            default_headers={"User-Agent": "cskh-telegram-bot/1.0"},
        ),
        system_prompt=build_system_prompt(settings.shop_name, texts["FAQ"], texts["menu"]),
        menu_text=texts["menu"],
    )

    async def post_init(application: Application) -> None:
        await db.open()
        await publish_command_menu(application.bot)
        application.bot_data[PURGE_TASK_KEY] = asyncio.create_task(
            _purge_loop(db, settings.history_retention_days)
        )

    async def post_shutdown(application: Application) -> None:
        task = application.bot_data.get(PURGE_TASK_KEY)
        if task:
            task.cancel()
        await db.close()

    application = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data[DEPS_KEY] = deps
    register_handlers(application)
    return application


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    # httpx logs full request URLs, which contain the Telegram bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    application = build_application(Settings.from_env())
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
