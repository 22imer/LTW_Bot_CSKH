"""Render the plain-text menu file as compact Telegram HTML messages with icon notes.

The source file (data/menu.txt) stays plain words so retrieval can match them; icons are
added only here, at display time.
"""
from __future__ import annotations

import html
import re

from .knowledge import fold

TELEGRAM_LIMIT = 4000  # real limit is 4096; keep headroom

CATEGORY_ICONS = (
    ("ca phe", "☕"),
    ("tra", "🍵"),
    ("sinh to", "🥤"),
    ("do xay", "🥤"),
    ("nuoc ep", "🍊"),
    ("banh", "🍰"),
    ("topping", "🧋"),
)
FLAG_ICONS = {
    "có caffeine": "⚡",
    "không caffeine": "🌿",
    "có sữa": "🥛",
    "không sữa": "🚫🥛",
    "đề xuất": "⭐",
}
LEGEND = "⚡ có caffeine · 🌿 không caffeine · 🥛 có sữa · 🚫🥛 không sữa · ⭐ quán đề xuất\nGiá tính bằng nghìn đồng (35k = 35.000đ)."

_ITEM = re.compile(r"^- (?P<name>[^(:]+?)(?: \((?P<prices>[^)]*)\))?: (?P<rest>.*)$")
_FLAGS = re.compile(r"\s*\[(?P<flags>[^\]]*)\]")
_TOPPINGS = re.compile(r"\s*Topping thêm: (?P<toppings>.*?)\.?\s*$")
_THOUSANDS = re.compile(r"\b(\d{1,3})\.000đ")


def _short_prices(text: str) -> str:
    """35.000đ -> 35k; other amounts are left alone."""
    return _THOUSANDS.sub(r"\1k", text)


def _category_icon(name: str) -> str:
    folded = fold(name)
    return next((icon for key, icon in CATEGORY_ICONS if key in folded), "▫️")


def _render_item(line: str) -> str:
    match = _ITEM.match(line)
    if match is None:
        return f"• {html.escape(_short_prices(line[2:]))}"
    rest = match["rest"]
    flags_match = _FLAGS.search(rest)
    flags = [f.strip() for f in flags_match["flags"].split(",")] if flags_match else []
    if flags_match:
        rest = _FLAGS.sub("", rest, count=1)
    toppings_match = _TOPPINGS.search(rest)
    toppings = toppings_match["toppings"] if toppings_match else ""
    if toppings_match:
        rest = _TOPPINGS.sub("", rest, count=1)
    description = rest.strip()

    icons = " ".join(FLAG_ICONS[f] for f in flags if f in FLAG_ICONS)
    prices = match["prices"]
    # Items without a "(sizes)" part (toppings) carry the price in `rest`.
    head = f"• <b>{html.escape(match['name'])}</b>"
    if prices:
        head += f" — {html.escape(_short_prices(prices).replace(' / ', ' · '))}"
    elif description and description.startswith("+"):
        head += f" {html.escape(_short_prices(description))}"
        description = ""
    if icons:
        head += f" {icons}"
    lines = [head]
    if description:
        lines.append(f"   {html.escape(description)}")
    if toppings:
        lines.append(f"   🧋 thêm: {html.escape(toppings)}")
    return "\n".join(lines)


def _blocks(menu_text: str) -> list[str]:
    """One block per heading, note line or item, so a split never cuts an item in half."""
    blocks: list[str] = []
    lines = [line.strip() for line in menu_text.strip().splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.startswith("## "):
            name = line[3:].strip()
            blocks.append(f"\n{_category_icon(name)} <b>{html.escape(name.upper())}</b>")
        elif line.startswith("- "):
            blocks.append(_render_item(line))
        elif index == 0:
            title = line.split(" (", 1)[0]
            blocks.append(f"☁️ <b>{html.escape(title)}</b>")
        else:
            blocks.append(f"<i>{html.escape(_short_prices(line))}</i>")
    blocks.append(f"\n{LEGEND}")
    return blocks


def menu_messages(menu_text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split the rendered menu into chunks under `limit`, breaking only between blocks."""
    chunks: list[str] = []
    current = ""
    for block in _blocks(menu_text):
        if current and len(current) + 1 + len(block) > limit:
            chunks.append(current.strip())
            current = block.lstrip("\n")
        else:
            current = f"{current}\n{block}" if current else block
    if current.strip():
        chunks.append(current.strip())
    return chunks
