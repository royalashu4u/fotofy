"""
All Telegram bot message & callback handlers for Fotofy AI.
Manages the full user journey: onboarding → selfie → style → generate → credits → payment.
"""

import io
import logging
from datetime import timezone
from typing import Optional

import httpx
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from bot import config
from bot.config import STYLE_PRESETS, PACKAGES, BOT_NAME
from bot.keyboards import (
    style_keyboard,
    after_generation_keyboard,
    no_credits_keyboard,
    upgrade_keyboard,
    confirm_purchase_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
)
from bot.services import firebase as db
from bot.services.pollinations import generate_image, generate_image_with_reference

logger = logging.getLogger(__name__)

# ── FSM States ────────────────────────────────────────────────
STATE_IDLE = "IDLE"
STATE_AWAITING_SELFIE = "AWAITING_SELFIE"
STATE_CHOOSING_STYLE = "CHOOSING_STYLE"
STATE_CUSTOM_PROMPT = "CUSTOM_PROMPT"
STATE_GENERATING = "GENERATING"


# ══════════════════════════════════════════════════════════════
# /start  — Onboarding
# ══════════════════════════════════════════════════════════════


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id

    # Register or fetch user
    profile = db.get_or_create_user(tg_id, user.first_name, user.username)
    credits = profile.get("credits", 0)
    is_new = (
        profile.get("total_generated", 0) == 0
        and credits == config.FREE_CREDITS_ON_SIGNUP
    )

    db.set_state(tg_id, STATE_IDLE)

    welcome_text = (
        f"👋 *Welcome to {BOT_NAME}!*\n\n"
        f"I turn your selfies into stunning AI art 🎨\n\n"
        f"{'🎁 You got *20 free credits* to get started!' if is_new else f'💎 You have *{credits} credits* remaining'}\n\n"
        f"Here's how it works:\n"
        f"1️⃣ Upload a *selfie* of yourself\n"
        f"2️⃣ Pick a *style* or type your own prompt\n"
        f"3️⃣ Get your *AI masterpiece* in seconds ✨\n\n"
        f"Ready? Let's create something amazing!"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


# ══════════════════════════════════════════════════════════════
# /generate — Trigger generation flow
# ══════════════════════════════════════════════════════════════


async def cmd_generate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await _start_generation_flow(update, ctx, user.id)


async def _start_generation_flow(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, tg_id: int
):
    """Common entry point for starting a generation."""
    profile = db.get_or_create_user(
        tg_id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    credits = profile.get("credits", 0)
    is_premium = profile.get("is_premium", False)

    # Check refill eligibility first
    if credits <= 0 and not is_premium:
        gifted = db.check_and_refill_credits(tg_id)
        if gifted:
            credits = config.REFILL_CREDITS
            await _send_or_edit(
                update,
                f"🎁 *You've been gifted {config.REFILL_CREDITS} free credits!*\n\n"
                f"Let's create some art!\n\nPlease upload your selfie 📸",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=cancel_keyboard(),
            )
            db.set_state(tg_id, STATE_AWAITING_SELFIE)
            return

    if credits <= 0 and not is_premium:
        # No credits — show upgrade options with timer
        remaining = db.time_until_refill(tg_id)
        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        await _send_or_edit(
            update,
            f"😔 *You're out of credits!*\n\n"
            f"You have two options:\n\n"
            f"⭐ *Upgrade now* to get more credits instantly\n"
            f"🎁 *Wait {config.REFILL_DAYS} days* for a free refill of {config.REFILL_CREDITS} credits\n\n"
            f"⏰ Free refill in: *{hours}h {minutes}m*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=no_credits_keyboard(hours, minutes),
        )
        return

    # Has credits — check if selfie is already on file
    selfie_file_id = profile.get("selfie_file_id")
    if selfie_file_id:
        # Skip selfie step, go straight to style
        db.set_state(tg_id, STATE_CHOOSING_STYLE, {"selfie_file_id": selfie_file_id})
        await _send_or_edit(
            update,
            f"🎨 *Choose your style!*\n\n"
            f"Pick a preset below or tap *Enter Custom Prompt* to write your own.\n\n"
            f"💎 Credits remaining: *{credits if not is_premium else '∞'}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=style_keyboard(),
        )
    else:
        db.set_state(tg_id, STATE_AWAITING_SELFIE)
        await _send_or_edit(
            update,
            "📸 *Upload your selfie!*\n\n"
            "Send me a clear photo of your face — I'll use it as the base for your AI portrait.\n\n"
            "_Tip: Use a well-lit, front-facing photo for the best results!_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cancel_keyboard(),
        )


# ══════════════════════════════════════════════════════════════
# Photo Handler — selfie upload
# ══════════════════════════════════════════════════════════════


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    state = db.get_state(tg_id)

    if state != STATE_AWAITING_SELFIE:
        # If not in selfie state, treat as a new generation request
        db.set_state(tg_id, STATE_AWAITING_SELFIE)
        await update.message.reply_text(
            "📸 Got a photo! Starting generation...\n\nNow choose your style:",
            reply_markup=style_keyboard(),
        )

    # Get highest-resolution photo
    photo = update.message.photo[-1]
    file_id = photo.file_id

    # Send typing action while processing
    await ctx.bot.send_chat_action(tg_id, ChatAction.UPLOAD_PHOTO)

    try:
        # Download selfie from Telegram and upload to Firebase Storage
        tg_file = await ctx.bot.get_file(file_id)
        image_bytes = await tg_file.download_as_bytearray()
        selfie_url = _upload_selfie_to_storage(tg_id, bytes(image_bytes))

        # Save selfie info
        db.save_selfie_info(tg_id, file_id, selfie_url)
        db.set_state(
            tg_id,
            STATE_CHOOSING_STYLE,
            {
                "selfie_file_id": file_id,
                "selfie_url": selfie_url,
            },
        )

        profile = db.get_user(tg_id)
        credits = profile.get("credits", 0)
        is_premium = profile.get("is_premium", False)

        await update.message.reply_text(
            f"✅ *Selfie saved!*\n\n"
            f"Now choose your style or enter a custom prompt:\n\n"
            f"💎 Credits remaining: *{credits if not is_premium else '∞'}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=style_keyboard(),
        )

    except Exception as e:
        logger.error(f"Error processing selfie for user {tg_id}: {e}")
        await update.message.reply_text(
            "❌ Couldn't process your photo. Please try again with a clearer image.",
            reply_markup=cancel_keyboard(),
        )


def _upload_selfie_to_storage(tg_id: int, image_bytes: bytes) -> str:
    """Upload selfie to local storage and return base64 data URL."""
    import base64
    import os

    os.makedirs("/tmp/selfies", exist_ok=True)
    file_path = f"/tmp/selfies/{tg_id}.jpg"

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


# ══════════════════════════════════════════════════════════════
# Text Handler — custom prompts
# ══════════════════════════════════════════════════════════════


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    state = db.get_state(tg_id)
    text = update.message.text.strip()

    # Ignore commands handled elsewhere
    if text.startswith("/"):
        return

    if state == STATE_CUSTOM_PROMPT:
        state_data = db.get_state_data(tg_id)
        selfie_url = state_data.get("selfie_url")

        # Start generating
        await _do_generation(
            update,
            ctx,
            tg_id,
            user_prompt=text,
            style_name="Custom",
            selfie_url=selfie_url,
        )

    elif state == STATE_IDLE:
        # Friendly nudge
        await update.message.reply_text(
            "👋 Tap *Generate Image* to get started!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "Please use the buttons to navigate, or /start to reset.",
            reply_markup=main_menu_keyboard(),
        )


# ══════════════════════════════════════════════════════════════
# Callback Query Handler — all button presses
# ══════════════════════════════════════════════════════════════


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    data = query.data

    # ── Style Selection ───────────────────────────────────────
    if data.startswith("style:"):
        style = data[len("style:") :]
        state_data = db.get_state_data(tg_id)
        selfie_url = state_data.get("selfie_url")

        if style == "custom":
            db.set_state(tg_id, STATE_CUSTOM_PROMPT, state_data)
            await query.edit_message_text(
                "✏️ *Enter your custom prompt:*\n\n"
                "Describe the image you want — be creative!\n\n"
                "_Example: 'A warrior standing on a mountain at sunset, epic painting'_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=cancel_keyboard(),
            )
        else:
            # Preset selected — start generation
            await _do_generation(
                update,
                ctx,
                tg_id,
                user_prompt=f"portrait of a person in {style} style",
                style_name=style,
                selfie_url=selfie_url,
                edit_message=True,
            )

    # ── Action Buttons ────────────────────────────────────────
    elif data.startswith("action:"):
        action = data[len("action:") :]

        if (
            action == "generate"
            or action == "generate_again"
            or action == "back_to_generate"
        ):
            await _start_generation_flow(update, ctx, tg_id)

        elif action == "credits":
            profile = db.get_user(tg_id)
            credits = profile.get("credits", 0) if profile else 0
            is_premium = profile.get("is_premium", False) if profile else False
            total = profile.get("total_generated", 0) if profile else 0
            remaining = db.time_until_refill(tg_id)
            total_secs = int(remaining.total_seconds())
            hours = total_secs // 3600
            minutes = (total_secs % 3600) // 60

            text = (
                f"💎 *Your Credits*\n\n"
                f"{'✨ Premium — Unlimited' if is_premium else f'Credits: *{credits}*'}\n"
                f"🖼️ Total generated: *{total}*\n"
            )
            if not is_premium and credits <= 0:
                text += f"\n⏰ Free refill in: *{hours}h {minutes}m*\n"
            elif not is_premium:
                text += f"\n🎁 Free refill every {config.REFILL_DAYS} days when you run out\n"

            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⭐ Get More Credits", callback_data="action:upgrade"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🎨 Generate", callback_data="action:generate"
                            )
                        ],
                    ]
                ),
            )

        elif action == "gallery":
            generations = db.get_recent_generations(tg_id, limit=5)
            if not generations:
                await query.edit_message_text(
                    "🖼️ *Your Gallery*\n\nNo images generated yet! Let's make some art 🎨",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🎨 Generate Now", callback_data="action:generate"
                                )
                            ]
                        ]
                    ),
                )
            else:
                await query.edit_message_text(
                    f"🖼️ *Your Gallery* — last {len(generations)} images\n\n"
                    + "\n".join(
                        f"{i + 1}. {g.get('style', 'Custom')} — [View]({g.get('image_url', '')})"
                        for i, g in enumerate(generations)
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🎨 Generate Again", callback_data="action:generate"
                                )
                            ]
                        ]
                    ),
                )

        elif action == "upgrade":
            await query.edit_message_text(
                "⭐ *Upgrade Fotofy AI*\n\n"
                "Choose a credit pack paid with Telegram Stars:\n\n"
                "⚡ *Starter* — 50 credits for quick projects\n"
                "🚀 *Pro* — 200 credits for power users\n"
                "♾️ *Unlimited* — 30 days of unlimited generation\n\n"
                "_Stars are purchased directly in Telegram — secure & instant_",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=upgrade_keyboard(),
            )

        elif action == "check_refill":
            gifted = db.check_and_refill_credits(tg_id)
            if gifted:
                await query.edit_message_text(
                    f"🎁 *Free credits gifted!*\n\nYou got {config.REFILL_CREDITS} credits. Let's create!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_menu_keyboard(),
                )
            else:
                remaining = db.time_until_refill(tg_id)
                total_secs = int(remaining.total_seconds())
                hours = total_secs // 3600
                minutes = (total_secs % 3600) // 60
                await query.answer(
                    f"Not yet! Free refill in {hours}h {minutes}m ⏰",
                    show_alert=True,
                )

        elif action == "cancel":
            db.set_state(tg_id, STATE_IDLE)
            await query.edit_message_text(
                "Cancelled. Tap *Generate Image* when you're ready!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )

    # ── Buy Package ───────────────────────────────────────────
    elif data.startswith("buy:"):
        pkg_id = data[len("buy:") :]
        pkg = next((p for p in PACKAGES if p["id"] == pkg_id), None)
        if not pkg:
            await query.answer("Invalid package", show_alert=True)
            return

        await query.edit_message_text(
            f"🛒 *{pkg['name']}*\n\n"
            f"{'Credits: ' + str(pkg['credits']) if pkg['credits'] < 999 else 'Unlimited for 30 days'}\n"
            f"Price: ⭐ *{pkg['stars']} Telegram Stars*\n\n"
            f"Tap confirm to complete the purchase securely via Telegram Stars.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=confirm_purchase_keyboard(pkg_id),
        )

    elif data.startswith("confirm_buy:"):
        pkg_id = data[len("confirm_buy:") :]
        await _send_stars_invoice(update, ctx, tg_id, pkg_id)


# ══════════════════════════════════════════════════════════════
# Core Generation Logic
# ══════════════════════════════════════════════════════════════


async def _do_generation(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    tg_id: int,
    user_prompt: str,
    style_name: str,
    selfie_url: Optional[str],
    edit_message: bool = False,
):
    """Run the full generation pipeline."""
    query = update.callback_query

    # ── Pre-flight credit check ───────────────────────────────
    success = db.deduct_credit(tg_id)
    if not success:
        await _start_generation_flow(update, ctx, tg_id)
        return

    db.set_state(tg_id, STATE_GENERATING)

    # ── Show "generating" message ─────────────────────────────
    generating_text = (
        f"🎨 *Generating your {style_name} masterpiece...*\n\n"
        f"This takes 10–30 seconds. Hang tight! ✨"
    )

    if edit_message and query:
        status_msg = await query.edit_message_text(
            generating_text, parse_mode=ParseMode.MARKDOWN
        )
        chat_id = query.message.chat_id
    else:
        msg = update.message or (query.message if query else None)
        if msg:
            status_msg = await ctx.bot.send_message(
                msg.chat_id, generating_text, parse_mode=ParseMode.MARKDOWN
            )
            chat_id = msg.chat_id
        else:
            return

    await ctx.bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)

    # ── Call Pollinations.ai ──────────────────────────────────
    try:
        if selfie_url:
            image_bytes, image_url = await generate_image_with_reference(
                prompt=user_prompt,
                reference_image_url=selfie_url,
                style_name=style_name if style_name != "Custom" else None,
            )
        else:
            image_bytes, image_url = await generate_image(
                prompt=user_prompt,
                style_name=style_name if style_name != "Custom" else None,
            )

        # Save to history
        db.save_generation(tg_id, user_prompt, style_name, image_url)
        db.set_state(tg_id, STATE_IDLE)

        # Get updated credits
        profile = db.get_user(tg_id)
        credits_left = profile.get("credits", 0) if profile else 0
        is_premium = profile.get("is_premium", False) if profile else False

        # ── Send generated image ──────────────────────────────
        caption = (
            f"✨ *Your {style_name} portrait is ready!*\n\n"
            f"💎 Credits remaining: *{credits_left if not is_premium else '∞'}*"
        )

        await ctx.bot.send_photo(
            chat_id=chat_id,
            photo=io.BytesIO(image_bytes),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=after_generation_keyboard(),
        )

        # Delete the "generating..." status message
        try:
            await ctx.bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass

        # Warn if credits are low
        if not is_premium and 0 < credits_left <= 3:
            await ctx.bot.send_message(
                chat_id,
                f"⚠️ *Running low!* You have only *{credits_left} credits* left.\n"
                f"Upgrade now to keep creating!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⭐ Upgrade", callback_data="action:upgrade"
                            )
                        ]
                    ]
                ),
            )

    except httpx.TimeoutException:
        db.set_state(tg_id, STATE_IDLE)
        # Refund the credit
        db.add_credits(tg_id, 1, "generation_timeout_refund")
        await ctx.bot.edit_message_text(
            "⏱️ Generation timed out. Your credit has been refunded!\n\nPlease try again.",
            chat_id=chat_id,
            message_id=status_msg.message_id,
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Generation error for user {tg_id}: {e}")
        db.set_state(tg_id, STATE_IDLE)
        db.add_credits(tg_id, 1, "generation_error_refund")
        await ctx.bot.edit_message_text(
            "❌ Generation failed. Your credit has been refunded!\n\nPlease try again.",
            chat_id=chat_id,
            message_id=status_msg.message_id,
            reply_markup=main_menu_keyboard(),
        )


# ══════════════════════════════════════════════════════════════
# Telegram Stars Payment
# ══════════════════════════════════════════════════════════════


async def _send_stars_invoice(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, tg_id: int, pkg_id: str
):
    pkg = next((p for p in PACKAGES if p["id"] == pkg_id), None)
    if not pkg:
        return

    query = update.callback_query
    chat_id = query.message.chat_id if query else tg_id

    credits_text = (
        f"{pkg['credits']} Credits" if pkg["credits"] < 999 else "Unlimited (30 days)"
    )

    await ctx.bot.send_invoice(
        chat_id=chat_id,
        title=f"Fotofy AI — {pkg['name']}",
        description=f"Get {credits_text} for AI portrait generation on Fotofy AI.",
        payload=f"purchase:{pkg_id}:{tg_id}",
        currency="XTR",
        prices=[{"label": pkg["name"], "amount": pkg["stars"]}],
        # No provider_token needed for Telegram Stars
    )


async def handle_pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Must respond OK within 10 seconds."""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def handle_successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Credits delivered after confirmed Stars payment."""
    tg_id = update.effective_user.id
    payment = update.message.successful_payment
    payload = payment.invoice_payload  # "purchase:{pkg_id}:{tg_id}"

    try:
        parts = payload.split(":")
        pkg_id = parts[1]
        pkg = next((p for p in PACKAGES if p["id"] == pkg_id), None)

        if pkg:
            db.apply_purchase(tg_id, pkg_id, pkg["credits"])
            credits_text = (
                f"{pkg['credits']} credits"
                if pkg["credits"] < 999
                else "unlimited access for 30 days"
            )

            await update.message.reply_text(
                f"🎉 *Payment successful!*\n\n"
                f"You've unlocked *{credits_text}*.\n\n"
                f"Go create something amazing! 🎨",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(),
            )
    except Exception as e:
        logger.error(f"Payment processing error for {tg_id}: {e}")
        await update.message.reply_text(
            "✅ Payment received! If credits don't appear, contact support with /help.",
        )


# ══════════════════════════════════════════════════════════════
# Other Commands
# ══════════════════════════════════════════════════════════════


async def cmd_credits(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    profile = db.get_or_create_user(
        tg_id, update.effective_user.first_name, update.effective_user.username
    )
    credits = profile.get("credits", 0)
    is_premium = profile.get("is_premium", False)
    total = profile.get("total_generated", 0)

    await update.message.reply_text(
        f"💎 *Your Credits*\n\n"
        f"{'✨ Premium — Unlimited' if is_premium else f'Credits remaining: *{credits}*'}\n"
        f"🖼️ Total images generated: *{total}*\n\n"
        f"{'Get more credits below!' if not is_premium else 'Enjoy unlimited generation!'}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⭐ Get More Credits", callback_data="action:upgrade"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🎨 Generate Now", callback_data="action:generate"
                    )
                ],
            ]
        ),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 *{BOT_NAME} Help*\n\n"
        f"*Commands:*\n"
        f"/start — Welcome & main menu\n"
        f"/generate — Create an AI image\n"
        f"/credits — Check your credit balance\n"
        f"/upgrade — Buy more credits\n"
        f"/gallery — View your recent images\n"
        f"/help — This help message\n\n"
        f"*How it works:*\n"
        f"1. Upload your selfie\n"
        f"2. Choose a style or type a prompt\n"
        f"3. Get your AI portrait!\n\n"
        f"*Credits:*\n"
        f"• New users get 20 free credits\n"
        f"• Each image costs 1 credit\n"
        f"• Free refill every {config.REFILL_DAYS} days when you run out\n\n"
        f"Issues? Contact @fotofyai\\_support",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


async def cmd_gallery(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    generations = db.get_recent_generations(tg_id, limit=5)

    if not generations:
        await update.message.reply_text(
            "🖼️ *Your Gallery*\n\nNo images yet! Generate your first AI portrait.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )
        return

    await update.message.reply_text(
        f"🖼️ *Your Gallery* (last {len(generations)} images)\n\n"
        + "\n".join(
            f"{i + 1}. {g.get('style', 'Custom')} — [View Image]({g.get('image_url', '')})"
            for i, g in enumerate(generations)
        ),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=False,
        reply_markup=main_menu_keyboard(),
    )


async def cmd_upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⭐ *Upgrade Fotofy AI*\n\n"
        "Get more credits with Telegram Stars:\n\n"
        "⚡ *Starter* — 50 credits → perfect for trying out styles\n"
        "🚀 *Pro* — 200 credits → for serious creators\n"
        "♾️ *Unlimited* — 30 days unlimited → best value!\n\n"
        "_All purchases are handled securely by Telegram_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=upgrade_keyboard(),
    )


async def cmd_paysupport(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Required by Telegram ToS for bots accepting Stars."""
    await update.message.reply_text(
        "💬 *Payment Support*\n\n"
        "Having issues with a Telegram Stars purchase?\n\n"
        "• Refund requests: Contact @fotofyai\\_support\n"
        "• Telegram Stars issues: @Telegram\n\n"
        "We'll resolve any issues within 24 hours!",
        parse_mode=ParseMode.MARKDOWN,
    )


# ══════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════


async def _send_or_edit(update: Update, text: str, **kwargs):
    """Edit message if from callback, send new message otherwise."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, **kwargs)
    elif update.message:
        await update.message.reply_text(text, **kwargs)
