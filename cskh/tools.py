"""Predefined tools the LLM agent may call. Nothing outside this list is reachable."""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .db import Database
from .knowledge import KnowledgeBase
from .stores import Stores

logger = logging.getLogger(__name__)

FEEDBACK_CATEGORIES = ("complaint", "suggestion", "other")
MAX_FEEDBACK_CHARS = 1000
MAX_SEARCH_RESULTS = 6

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_stores",
            "description": "Lấy danh sách các cơ sở (store_id, tên, địa chỉ, giờ mở cửa). "
            "Luôn gọi tool này trước khi trả lời về địa chỉ hoặc giờ mở cửa.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_store_contact",
            "description": "Gửi danh thiếp liên hệ (số điện thoại) của một cơ sở cho khách "
            "trong Telegram. Cần store_id lấy từ list_stores.",
            "parameters": {
                "type": "object",
                "properties": {"store_id": {"type": "string"}},
                "required": ["store_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_feedback",
            "description": "Ghi nhận góp ý hoặc khiếu nại của khách để quán xem xét.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": list(FEEDBACK_CATEGORIES)},
                    "content": {"type": "string", "description": "Nội dung góp ý, ngắn gọn."},
                },
                "required": ["category", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Tra cứu tài liệu của quán: thực đơn (món, size, giá, topping, "
            "caffeine, sữa) và cách quán vận hành (gọi món tại bàn, mang đi, đặt bàn, "
            "thanh toán, hủy đơn). Truyền vài từ khóa tiếng Việt ngắn gọn như tên món hoặc "
            "chủ đề, ví dụ 'cappuccino', 'đặt bàn', 'chuyển khoản'. Trả về tối đa 6 đoạn "
            "liên quan nhất; có thể gọi lại với từ khóa khác nếu chưa thấy thông tin.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

SendContact = Callable[[str], Awaitable[None]]


@dataclass
class ToolContext:
    user_id: int
    stores: Stores
    db: Database
    knowledge: KnowledgeBase
    send_contact: SendContact


def _result(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


async def execute_tool(name: str, raw_arguments: str, ctx: ToolContext) -> str:
    """Run one tool call and return a JSON string for the LLM. Never raises."""
    try:
        arguments = json.loads(raw_arguments) if raw_arguments else {}
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")
    except (json.JSONDecodeError, ValueError):
        return _result(error="Tham số không hợp lệ.")

    if name == "list_stores":
        return _result(
            stores=[
                {
                    "store_id": store_id,
                    "name": store["name"],
                    "address": store["address"],
                    "hours": store["hours"],
                }
                for store_id, store in ctx.stores.items()
            ]
        )

    if name == "get_store_contact":
        store_id = str(arguments.get("store_id", ""))
        if store_id not in ctx.stores:
            return _result(error="Không tìm thấy cơ sở.", valid_store_ids=list(ctx.stores))
        try:
            await ctx.send_contact(store_id)
        except Exception:  # Telegram errors must not break the agent loop
            logger.exception("Could not send contact card")
            return _result(error="Không gửi được danh thiếp.")
        return _result(ok=True, note="Đã gửi danh thiếp liên hệ cho khách.")

    if name == "search_knowledge":
        query = str(arguments.get("query", "")).strip()[:200]
        chunks = ctx.knowledge.search(query, limit=MAX_SEARCH_RESULTS)
        if not chunks:
            return _result(results=[], note="Không tìm thấy thông tin phù hợp trong tài liệu.")
        return _result(results=[{"source": c.source, "text": c.text} for c in chunks])

    if name == "submit_feedback":
        category = str(arguments.get("category", "other"))
        if category not in FEEDBACK_CATEGORIES:
            category = "other"
        content = str(arguments.get("content", "")).strip()[:MAX_FEEDBACK_CHARS]
        if not content:
            return _result(error="Nội dung góp ý trống.")
        feedback_id = await ctx.db.add_feedback(ctx.user_id, category, content)
        return _result(ok=True, feedback_id=feedback_id)

    return _result(error=f"Tool không tồn tại: {name}")
