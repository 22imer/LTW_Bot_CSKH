"""Store data loading and formatting."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = frozenset({"name", "address", "phone", "hours"})

Stores = dict[str, dict[str, str]]


def load_stores(path: Path) -> Stores:
    """Load branch data from JSON, validating required fields."""
    try:
        with path.open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read store data from {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Store data in {path} must be a JSON object")
    stores: Stores = {}
    for store_id, info in raw.items():
        if not isinstance(info, dict) or not REQUIRED_FIELDS.issubset(info):
            raise ValueError(f"Store {store_id!r} must contain {sorted(REQUIRED_FIELDS)}")
        phone = str(info["phone"])
        if not phone.startswith("+"):
            raise ValueError(f"Store {store_id!r} phone must be in international format (+84...)")
        stores[store_id] = {key: str(info[key]) for key in REQUIRED_FIELDS}
    return stores


def format_addresses_html(stores: Stores) -> str:
    lines = ["📍 <b>DANH SÁCH ĐỊA CHỈ CÁC CỬA HÀNG</b>\n"]
    for store in stores.values():
        lines.append(
            f"🔹 <b>{html.escape(store['name'])}</b>\n"
            f"   • Địa chỉ: {html.escape(store['address'])}\n"
            f"   • Giờ mở cửa: {html.escape(store['hours'])}\n"
        )
    return "\n".join(lines)


def build_vcard(store: dict[str, str]) -> str:
    return (
        "BEGIN:VCARD\r\nVERSION:3.0\r\n"
        f"FN:{store['name']}\r\n"
        f"TEL;TYPE=WORK,VOICE:{store['phone']}\r\n"
        f"ADR;TYPE=WORK:;;{store['address']};;;;\r\n"
        f"NOTE:Giờ mở cửa: {store['hours']}\r\nEND:VCARD"
    )
