"""Render the plain-text menu file as Telegram HTML messages."""
from __future__ import annotations

import html

TELEGRAM_LIMIT = 4000  # real limit is 4096; keep headroom


def _format_line(line: str) -> str:
    if line.startswith("## "):
        return f"<b>{html.escape(line[3:])}</b>"
    return html.escape(line)


def menu_messages(menu_text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split the menu into HTML chunks under `limit`, breaking only between lines."""
    chunks: list[str] = []
    current = ""
    for line in menu_text.strip().splitlines():
        formatted = _format_line(line)
        if current and len(current) + 1 + len(formatted) > limit:
            chunks.append(current)
            current = formatted
        else:
            current = f"{current}\n{formatted}" if current else formatted
    if current:
        chunks.append(current)
    return chunks
