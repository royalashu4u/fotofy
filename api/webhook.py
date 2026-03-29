"""
Vercel serverless entry point for Fotofy AI Telegram Bot.
Handles all incoming Telegram webhook updates via FastAPI.
"""

import json
import logging
import asyncio
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
)

from bot.config import BOT_TOKEN, WEBHOOK_SECRET
from bot.handlers import (
    cmd_start,
    cmd_generate,
    cmd_credits,
    cmd_help,
    cmd_gallery,
    cmd_upgrade,
    cmd_paysupport,
    handle_photo,
    handle_text,
    handle_callback,
    handle_pre_checkout,
    handle_successful_payment,
)

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(title="Fotofy AI Bot", docs_url=None, redoc_url=None)

# ── Build PTB Application (once, module-level) ────────────────
ptb_app = Application.builder().token(BOT_TOKEN).build()

# Register all handlers
ptb_app.add_handler(CommandHandler("start",       cmd_start))
ptb_app.add_handler(CommandHandler("generate",    cmd_generate))
ptb_app.add_handler(CommandHandler("credits",     cmd_credits))
ptb_app.add_handler(CommandHandler("help",        cmd_help))
ptb_app.add_handler(CommandHandler("gallery",     cmd_gallery))
ptb_app.add_handler(CommandHandler("upgrade",     cmd_upgrade))
ptb_app.add_handler(CommandHandler("paysupport",  cmd_paysupport))

ptb_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
ptb_app.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND, handle_text
))

ptb_app.add_handler(CallbackQueryHandler(handle_callback))
ptb_app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
ptb_app.add_handler(MessageHandler(
    filters.SUCCESSFUL_PAYMENT, handle_successful_payment
))


# ── Webhook Endpoint ──────────────────────────────────────────

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """
    Main webhook — receives all Telegram updates.
    Vercel routes all POST /api/webhook here.
    The secret token header is validated for security.
    """
    # Verify Telegram secret token
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        logger.warning("Invalid secret token received")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        update = Update.de_json(body, ptb_app.bot)

        # Initialize the app if not already done (needed for Vercel cold starts)
        if not ptb_app._initialized:
            await ptb_app.initialize()

        await ptb_app.process_update(update)

    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        # Always return 200 to Telegram — never let it retry a broken update
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

    return JSONResponse({"ok": True})


# ── Health Check ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "Fotofy AI Bot is running 🎨", "ok": True}


@app.get("/api/health")
async def health():
    return {"status": "ok", "bot": "Fotofy AI"}


# ── Webhook Setup Endpoint (call once to register) ────────────

@app.get("/api/setup")
async def setup_webhook(request: Request):
    """
    Call this endpoint once after deploying to Vercel to register the webhook.
    Example: GET https://your-app.vercel.app/api/setup
    """
    from bot.config import WEBHOOK_URL

    webhook_url = f"{WEBHOOK_URL}/api/webhook"

    # Set webhook
    await ptb_app.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )

    # Set bot commands menu
    await ptb_app.bot.set_my_commands([
        BotCommand("start",      "🏠 Start & onboarding"),
        BotCommand("generate",   "🎨 Generate an AI image"),
        BotCommand("credits",    "💎 Check your credits"),
        BotCommand("gallery",    "🖼️ View your images"),
        BotCommand("upgrade",    "⭐ Buy more credits"),
        BotCommand("help",       "❓ Help & support"),
        BotCommand("paysupport", "💬 Payment support"),
    ])

    info = await ptb_app.bot.get_webhook_info()
    return {
        "ok": True,
        "webhook_url": webhook_url,
        "webhook_info": {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
        },
    }


# ── Vercel handler (ASGI entrypoint) ──────────────────────────
# Vercel expects a module-level `app` variable for ASGI — we already have it.
