"""Environment-driven settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PLACEHOLDER_TOKEN = "replace_with_your_bot_token"
PLACEHOLDER_LLM_KEY = "replace_with_your_llm_api_key"


@dataclass(frozen=True)
class Settings:
    bot_token: str
    llm_api_key: str
    llm_model: str
    llm_base_url: str | None
    shop_name: str
    faq_file: Path
    menu_file: Path
    stores_file: Path
    db_path: Path
    history_limit: int = 10
    history_retention_days: int = 30
    rate_limit_messages: int = 10
    rate_limit_window_seconds: float = 60.0
    max_message_chars: int = 1000
    max_tool_rounds: int = 3
    llm_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            bot_token=os.getenv("BOT_TOKEN", "").strip(),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "").strip() or None,
            shop_name=os.getenv("SHOP_NAME", "Mây Cafe").strip() or "Mây Cafe",
            faq_file=Path(os.getenv("FAQ_FILE", "data/faq.md")),
            menu_file=Path(os.getenv("MENU_FILE", "data/menu.txt")),
            stores_file=Path(os.getenv("STORES_FILE", "data/stores.json")),
            db_path=Path(os.getenv("DB_PATH", "data/cskh.sqlite3")),
        )

    def validate(self) -> None:
        if not self.bot_token or self.bot_token == PLACEHOLDER_TOKEN:
            raise RuntimeError("Set BOT_TOKEN in .env before starting the bot")
        if not self.llm_api_key or self.llm_api_key == PLACEHOLDER_LLM_KEY:
            raise RuntimeError("Set LLM_API_KEY in .env before starting the bot")
