import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ─────────────────────────────────────────────────
BOT_TOKEN: str = os.environ["BOT_TOKEN"]
WEBHOOK_URL: str = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "fotofyai_secret")

# ── Firebase ──────────────────────────────────────────────────
FIREBASE_PROJECT_ID: str = os.environ.get("FIREBASE_PROJECT_ID", "")
FIREBASE_STORAGE_BUCKET: str = os.environ.get("FIREBASE_STORAGE_BUCKET", "")
FIREBASE_CREDENTIALS_PATH: str = os.environ.get(
    "FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json"
)
FIREBASE_CREDENTIALS_JSON: str = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")

# ── Pollinations.ai ───────────────────────────────────────────
POLLINATIONS_API_KEY: str = os.environ.get("POLLINATIONS_API_KEY", "")
POLLINATIONS_MODEL: str = os.environ.get("POLLINATIONS_MODEL", "flux")
POLLINATIONS_WIDTH: int = int(os.environ.get("POLLINATIONS_WIDTH", "1024"))
POLLINATIONS_HEIGHT: int = int(os.environ.get("POLLINATIONS_HEIGHT", "1024"))

# ── Credit System ─────────────────────────────────────────────
FREE_CREDITS_ON_SIGNUP: int = int(os.environ.get("FREE_CREDITS_ON_SIGNUP", "20"))
REFILL_CREDITS: int = int(os.environ.get("REFILL_CREDITS", "20"))
REFILL_DAYS: int = int(os.environ.get("REFILL_DAYS", "3"))

# ── Bot Metadata ──────────────────────────────────────────────
BOT_NAME = "Fotofy AI"
BOT_USERNAME = "fotofyai_bot"

# ── Style Presets ─────────────────────────────────────────────
STYLE_PRESETS = {
    "🌸 Anime": (
        "anime style portrait, vibrant colors, detailed eyes, Studio Ghibli inspired, "
        "soft lighting, cinematic composition, highly detailed"
    ),
    "🤖 Cyberpunk": (
        "cyberpunk portrait, neon lights, futuristic city background, holographic elements, "
        "dark atmosphere, rain, high tech, blade runner aesthetic, ultra realistic"
    ),
    "🧝 Fantasy": (
        "epic fantasy portrait, magical aura, ethereal lighting, enchanted forest background, "
        "highly detailed, painterly, cinematic, mystical"
    ),
    "📸 Pro Portrait": (
        "professional studio portrait photography, perfect lighting, bokeh background, "
        "8K quality, DSLR, magazine cover, sharp focus, photorealistic"
    ),
    "🎨 Oil Painting": (
        "oil painting portrait, Renaissance style, rich colors, dramatic lighting, "
        "masterpiece, museum quality, fine art, detailed brushstrokes"
    ),
    "🌆 Neon City": (
        "portrait in neon lit city at night, vibrant neon reflections, rain on streets, "
        "moody atmosphere, cinematic, ultra detailed, 8K"
    ),
    "👾 Pixel Art": (
        "pixel art portrait, retro 16-bit style, detailed pixels, vibrant colors, "
        "video game character art, nostalgic, cute"
    ),
    "🏛️ Renaissance": (
        "Renaissance oil painting portrait, classical composition, dramatic chiaroscuro lighting, "
        "old masters style, museum quality, detailed, 16th century aesthetic"
    ),
    "🐉 Dragon Realm": (
        "epic dragon rider portrait, fantasy epic scene, glowing dragon scales in background, "
        "magical fire, heroic pose, cinematic lighting, ultra detailed"
    ),
    "🌊 Watercolor": (
        "beautiful watercolor portrait, soft colors blending, artistic, dreamy aesthetic, "
        "flowing paint, professional watercolor technique"
    ),
}

# ── Upgrade Packages ──────────────────────────────────────────
PACKAGES = [
    {
        "id": "starter",
        "name": "⚡ Starter Pack",
        "credits": 50,
        "stars": 99,
        "label": "50 Credits — ⭐ 99 Stars",
    },
    {
        "id": "pro",
        "name": "🚀 Pro Pack",
        "credits": 200,
        "stars": 299,
        "label": "200 Credits — ⭐ 299 Stars",
    },
    {
        "id": "monthly",
        "name": "♾️ Unlimited Month",
        "credits": 999,
        "stars": 499,
        "label": "Unlimited 30 days — ⭐ 499 Stars",
    },
]
