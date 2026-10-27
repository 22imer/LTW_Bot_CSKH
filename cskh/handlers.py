"""Telegram handlers: menu shortcuts, command shortcuts, agent chat."""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass

from telegram import (
    Bot,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonCommands,
    Message,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .agent import AgentError, ChatClient, run_agent
from .config import Settings
from .db import Database
from .knowledge import KnowledgeBase
from .menu import menu_messages
from .ratelimit import RateLimiter
from .stores import Stores, build_vcard, format_addresses_html
from .tools import ToolContext

logger = logging.getLogger(__name__)

DEPS_KEY = "deps"

MSG_RATE_LIMITED = "⏳ Bạn nhắn nhanh quá, Mây theo không kịp. Đợi Mây một chút rồi nhắn lại nhé."
MSG_TOO_LONG = "✂️ Tin nhắn dài quá {limit} ký tự. Bạn chia nhỏ hoặc rút gọn giúp Mây nhé."
MSG_LLM_ERROR = (
    "⚠️ Xin lỗi bạn, Mây đang gặp sự cố nên chưa trả lời được. "
    "Bạn thử nhắn lại sau ít phút, hoặc gõ /start để xem địa chỉ và liên hệ quán nhé."
)
MSG_TEXT_ONLY = "Mây chỉ đọc được tin nhắn chữ thôi. Bạn gõ câu hỏi giúp Mây nhé ☁️"
CONTACT_MENU_TEXT = "📞 <b>LIÊN HỆ CỬA HÀNG</b>\n\nVui lòng chọn cơ sở bạn muốn gọi điện:"


@dataclass
class Deps:
    settings: Settings
    stores: Stores
    db: Database
    limiter: RateLimiter
    llm: ChatClient
    system_prompt: str
    menu_text: str
    knowledge: KnowledgeBase


def get_deps(context: ContextTypes.DEFAULT_TYPE) -> Deps:
    return context.application.bot_data[DEPS_KEY]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Liên hệ cửa hàng", callback_data="menu_contact")],
        [InlineKeyboardButton("📍 Địa chỉ cửa hàng", callback_data="menu_address")],
    ])


def store_selection_keyboard(stores: Stores) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"🏪 {store['name']}", callback_data=f"contact_{store_id}")]
        for store_id, store in stores.items()
    ]
    rows.append([InlineKeyboardButton("⬅️ Quay lại Menu chính", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


async def send_store_contact(
    bot: Bot,
    chat_id: int,
    store: dict[str, str],
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    # send_contact, not a tel: URL button: Telegram rejects tel: in inline buttons.
    await bot.send_contact(
        chat_id=chat_id,
        phone_number=store["phone"],
        first_name=store["name"][:64],
        vcard=build_vcard(store),
        reply_markup=reply_markup,
    )


async def send_or_edit_text(
    query, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup: InlineKeyboardMarkup
) -> None:
    """Edit a text menu; delete a contact/non-text message and send a new menu."""
    message = query.message
    if message is None:
        return
    if isinstance(message, Message):
        if message.text is not None:
            try:
                await query.edit_message_text(
                    text=text, reply_markup=reply_markup, parse_mode="HTML"
                )
            except TelegramError:
                # e.g. "message is not modified" when the same menu is tapped twice
                logger.debug("Could not edit menu message", exc_info=True)
            return
        try:
            await message.delete()
        except TelegramError:
            logger.debug("Could not delete previous non-text message", exc_info=True)
    # Inaccessible (too old) messages cannot be edited or deleted: just send a new menu.
    await context.bot.send_message(
        chat_id=message.chat.id, text=text, reply_markup=reply_markup, parse_mode="HTML"
    )

async def _remember_user(deps: Deps, update: Update) -> None:
    user = update.effective_user
    if user:
        await deps.db.upsert_user(user.id, user.first_name, user.username)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await _remember_user(get_deps(context), update)
    user = update.effective_user
    name = html.escape(user.first_name if user else "bạn")
    shop_name = html.escape(get_deps(context).settings.shop_name)
    await message.reply_text(
        f"Chào <b>{name}</b> ☁️\n"
        f"Mây là trợ lý của {shop_name}. Bạn cần hỏi địa chỉ, giờ mở cửa, cách đặt mang đi, "
        "đặt bàn hay góp ý cho quán đều nhắn cho Mây nhé.\n\n"
        "Hoặc chọn nhanh bên dưới:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def address_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        format_addresses_html(get_deps(context).stores),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    chunks = menu_messages(get_deps(context).menu_text)
    for index, chunk in enumerate(chunks):
        # Main-menu buttons only under the last chunk.
        markup = main_menu_keyboard() if index == len(chunks) - 1 else None
        await message.reply_text(chunk, reply_markup=markup, parse_mode="HTML")


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        CONTACT_MENU_TEXT,
        reply_markup=store_selection_keyboard(get_deps(context).stores),
        parse_mode="HTML",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    deps = get_deps(context)
    data = query.data or ""

    if data == "menu_main":
        await send_or_edit_text(
            query, context, "Vui lòng chọn một mục bên dưới:", main_menu_keyboard()
        )
    elif data == "menu_address":
        await send_or_edit_text(
            query, context, format_addresses_html(deps.stores), main_menu_keyboard()
        )
    elif data == "menu_contact":
        await send_or_edit_text(
            query, context, CONTACT_MENU_TEXT, store_selection_keyboard(deps.stores)
        )
    elif data.startswith("contact_"):
        store = deps.stores.get(data.removeprefix("contact_"))
        if store is None:
            await send_or_edit_text(
                query, context, "Không tìm thấy thông tin cửa hàng.", main_menu_keyboard()
            )
            return
        message = query.message
        if message is None:
            return
        if isinstance(message, Message):
            try:
                await message.delete()
            except TelegramError:
                logger.debug("Could not delete old store menu", exc_info=True)
        chat_id = message.chat.id
        navigation = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Chọn cửa hàng khác", callback_data="menu_contact")],
            [InlineKeyboardButton("🏠 Về Menu chính", callback_data="menu_main")],
        ])
        try:
            await send_store_contact(context.bot, chat_id, store, navigation)
        except TelegramError:
            logger.exception("Could not send contact card")
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Chưa gửi được danh thiếp. Vui lòng thử lại sau.",
                reply_markup=main_menu_keyboard(),
            )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or not message.text:
        return
    deps = get_deps(context)
    settings = deps.settings

    if len(message.text) > settings.max_message_chars:
        await message.reply_text(MSG_TOO_LONG.format(limit=settings.max_message_chars))
        return
    if not deps.limiter.allow(user.id):
        await message.reply_text(MSG_RATE_LIMITED)
        return

    await _remember_user(deps, update)
    try:
        await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)
    except TelegramError:
        logger.debug("Could not send typing action", exc_info=True)

    history = await deps.db.recent_messages(user.id, settings.history_limit)
    tool_ctx = ToolContext(
        user_id=user.id,
        stores=deps.stores,
        db=deps.db,
        knowledge=deps.knowledge,
        send_contact=_contact_sender(context.bot, message, deps.stores),
    )
    try:
        reply = await run_agent(
            deps.llm,
            settings.llm_model,
            history,
            message.text,
            tool_ctx,
            system_prompt=deps.system_prompt,
            max_tool_rounds=settings.max_tool_rounds,
            timeout=settings.llm_timeout_seconds,
        )
    except AgentError:
        logger.exception("Agent failed")
        await message.reply_text(MSG_LLM_ERROR)
        return

    await deps.db.add_message(user.id, "user", message.text)
    await deps.db.add_message(user.id, "assistant", reply)
    # Plain text on purpose: LLM output is untrusted, so no parse_mode.
    try:
        await message.reply_text(reply)
    except TelegramError:
        logger.exception("Could not send agent reply")


def _contact_sender(bot: Bot, message: Message, stores: Stores):
    async def send(store_id: str) -> None:
        await send_store_contact(bot, message.chat_id, stores[store_id])

    return send


async def unsupported_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message:
        await message.reply_text(MSG_TEXT_ONLY)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error while processing update", exc_info=context.error)


# Shown in Telegram's menu button next to the message box. Command names must be
# lowercase ASCII, hence /diachi and /lienhe.
BOT_COMMANDS = [
    BotCommand("start", "Mở menu chính của Mây"),
    BotCommand("menu", "Xem thực đơn và giá"),
    BotCommand("diachi", "Địa chỉ và giờ mở cửa các cơ sở"),
    BotCommand("lienhe", "Nhận số điện thoại của cơ sở"),
]


async def publish_command_menu(bot: Bot) -> None:
    """Fill the hamburger menu with BOT_COMMANDS. Failure is non-fatal."""
    try:
        await bot.set_my_commands(BOT_COMMANDS)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except TelegramError:
        logger.warning("Could not publish the command menu", exc_info=True)


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("diachi", address_command))
    application.add_handler(CommandHandler("lienhe", contact_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(
        MessageHandler(
            ~filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.ALL, unsupported_handler
        )
    )
    application.add_error_handler(error_handler)
