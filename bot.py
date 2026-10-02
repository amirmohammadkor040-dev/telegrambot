"""A small Telegram inbox bot that forwards visitor messages to its owner."""

import html
import logging
import os
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    token: str
    owner_id: int


def load_settings() -> Settings:
    """Load and validate the bot credentials before connecting to Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    owner_id = os.getenv("OWNER_TELEGRAM_ID")

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not owner_id:
        raise RuntimeError("OWNER_TELEGRAM_ID is required.")

    try:
        return Settings(token=token, owner_id=int(owner_id))
    except ValueError as exc:
        raise RuntimeError("OWNER_TELEGRAM_ID must be a numeric Telegram user ID.") from exc


def sender_label(update: Update) -> str:
    """Create a safe, readable identity label for the owner notification."""
    user = update.effective_user
    if user is None:
        return "کاربر ناشناس"

    name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    username = f"@{user.username}" if user.username else "بدون نام کاربری"
    name = html.escape(name or "بدون نام")
    username = html.escape(username)
    return f"{name} ({username} | <code>{user.id}</code>)"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet visitors and explain how to use the inbox."""
    if update.message:
        await update.message.reply_text(
            "سلام! پیام‌تان را همین‌جا بفرستید؛ به صاحب بات می‌رسد."
        )


async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward every non-command visitor message to the configured owner."""
    message = update.effective_message
    user = update.effective_user
    settings: Settings = context.application.bot_data["settings"]

    if message is None or user is None:
        return

    if user.id == settings.owner_id:
        await message.reply_text("این پیام از طرف صاحب بات است و ارسال نشد.")
        return

    await context.bot.send_message(
        chat_id=settings.owner_id,
        text=f"📩 <b>پیام جدید از</b> {sender_label(update)}",
        parse_mode=ParseMode.HTML,
    )
    await context.bot.forward_message(
        chat_id=settings.owner_id,
        from_chat_id=message.chat_id,
        message_id=message.message_id,
    )
    await message.reply_text("✅ پیام شما ارسال شد. ممنون!")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unexpected errors without exposing implementation details to users."""
    logger.exception("Unhandled exception while processing an update", exc_info=context.error)


def main() -> None:
    settings = load_settings()
    application = Application.builder().token(settings.token).build()
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, receive_message))
    application.add_error_handler(error_handler)

    logger.info("Starting inbox bot for owner ID %s", settings.owner_id)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
