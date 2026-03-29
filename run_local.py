"""
Local development runner.
Runs the bot in polling mode (no webhook needed for local testing).
"""

import asyncio
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
)
from telegram import BotCommand

from bot.config import BOT_TOKEN
from bot.handlers import (
    cmd_start, cmd_generate, cmd_credits, cmd_help,
    cmd_gallery, cmd_upgrade, cmd_paysupport,
    handle_photo, handle_text, handle_callback,
    handle_pre_checkout, handle_successful_payment,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("generate",   cmd_generate))
    app.add_handler(CommandHandler("credits",    cmd_credits))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("gallery",    cmd_gallery))
    app.add_handler(CommandHandler("upgrade",    cmd_upgrade))
    app.add_handler(CommandHandler("paysupport", cmd_paysupport))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

    # Set bot commands
    await app.bot.set_my_commands([
        BotCommand("start",      "🏠 Start & onboarding"),
        BotCommand("generate",   "🎨 Generate an AI image"),
        BotCommand("credits",    "💎 Check your credits"),
        BotCommand("gallery",    "🖼️ View your images"),
        BotCommand("upgrade",    "⭐ Buy more credits"),
        BotCommand("help",       "❓ Help & support"),
        BotCommand("paysupport", "💬 Payment support"),
    ])

    print("🎨 Fotofy AI Bot started in POLLING mode...")
    print("Press Ctrl+C to stop.\n")

    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
