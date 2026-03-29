"""
Keyboard builders — all inline keyboards and reply keyboards for Fotofy AI.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot.config import STYLE_PRESETS, PACKAGES


# ── Style Preset Keyboard ─────────────────────────────────────

def style_keyboard() -> InlineKeyboardMarkup:
    """Grid of style preset buttons + custom prompt option."""
    style_names = list(STYLE_PRESETS.keys())
    rows = []

    # Two columns per row
    for i in range(0, len(style_names), 2):
        row = [
            InlineKeyboardButton(style_names[i], callback_data=f"style:{style_names[i]}"),
        ]
        if i + 1 < len(style_names):
            row.append(
                InlineKeyboardButton(style_names[i + 1], callback_data=f"style:{style_names[i + 1]}")
            )
        rows.append(row)

    # Custom prompt button at the bottom
    rows.append([
        InlineKeyboardButton("✏️ Enter Custom Prompt", callback_data="style:custom")
    ])

    return InlineKeyboardMarkup(rows)


# ── Generate Again / Back ─────────────────────────────────────

def after_generation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎨 Generate Again", callback_data="action:generate_again"),
            InlineKeyboardButton("💎 My Credits", callback_data="action:credits"),
        ],
        [
            InlineKeyboardButton("🖼️ My Gallery", callback_data="action:gallery"),
            InlineKeyboardButton("🛒 Upgrade", callback_data="action:upgrade"),
        ],
    ])


# ── No Credits Keyboard ───────────────────────────────────────

def no_credits_keyboard(hours_left: int, minutes_left: int) -> InlineKeyboardMarkup:
    if hours_left > 0:
        timer_label = f"⏰ Free Refill in {hours_left}h {minutes_left}m"
    elif minutes_left > 0:
        timer_label = f"⏰ Free Refill in {minutes_left} minutes"
    else:
        timer_label = "🎁 Claim Free Credits Now!"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Upgrade Now", callback_data="action:upgrade")],
        [InlineKeyboardButton(timer_label, callback_data="action:check_refill")],
    ])


# ── Upgrade Packages Keyboard ─────────────────────────────────

def upgrade_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for pkg in PACKAGES:
        rows.append([
            InlineKeyboardButton(pkg["label"], callback_data=f"buy:{pkg['id']}")
        ])
    rows.append([
        InlineKeyboardButton("« Back", callback_data="action:back_to_generate")
    ])
    return InlineKeyboardMarkup(rows)


# ── Confirm Purchase ──────────────────────────────────────────

def confirm_purchase_keyboard(package_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Pay with ⭐ Stars", callback_data=f"confirm_buy:{package_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="action:upgrade")],
    ])


# ── Start / Main Menu ─────────────────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Generate Image", callback_data="action:generate")],
        [
            InlineKeyboardButton("💎 My Credits", callback_data="action:credits"),
            InlineKeyboardButton("🖼️ My Gallery", callback_data="action:gallery"),
        ],
        [InlineKeyboardButton("⭐ Upgrade Plan", callback_data="action:upgrade")],
    ])


# ── Cancel Button ──────────────────────────────────────────────

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="action:cancel")]
    ])
