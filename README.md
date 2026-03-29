# 🎨 Fotofy AI — Telegram Image Generator Bot

> Turn any selfie into stunning AI art. Powered by **Pollinations.ai** (free), deployed on **Vercel**, powered by **Firebase**.

---

## ✨ Features

- 📸 **Selfie upload** — users send their photo as a reference
- 🎨 **10 style presets** — Anime, Cyberpunk, Fantasy, Oil Painting, Neon City, and more
- ✏️ **Custom prompts** — type anything you imagine
- 💎 **Credit system** — 20 free credits on signup
- 🎁 **Auto refill** — free 20 credits every 3 days when empty
- ⭐ **Telegram Stars payments** — upgrade packs (50 / 200 / Unlimited)
- 🔥 **Firebase Firestore** — user data, credits, history
- ☁️ **Vercel deployment** — serverless, auto-scales, free tier

---

## 🏗️ Project Structure

```
fotofyai/
├── api/
│   └── webhook.py          # Vercel entry point (FastAPI ASGI)
├── bot/
│   ├── config.py           # All settings, presets, packages
│   ├── handlers.py         # All message & callback handlers
│   ├── keyboards.py        # All inline keyboard builders
│   └── services/
│       ├── firebase.py     # Firestore + Storage operations
│       └── pollinations.py # AI image generation (free API)
├── run_local.py            # Local polling runner
├── admin.py                # CLI admin tool
├── requirements.txt
├── vercel.json
└── .env.example
```

---

## 🚀 Setup Guide

### Step 1 — Create Telegram Bot

1. Open Telegram → search `@BotFather`
2. Send `/newbot` → follow instructions
3. Copy your **Bot Token** (looks like `123456:ABC-DEF...`)

### Step 2 — Set Up Firebase

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a new project (e.g. `fotofyai`)
3. Enable **Firestore Database** (Production mode is fine)
4. Enable **Firebase Storage**
5. Go to **Project Settings → Service Accounts**
6. Click **Generate new private key** → download the JSON file
7. Rename it to `firebase-credentials.json` and place it in the project root

#### Firebase Storage Rules
In Firebase Console → Storage → Rules, set:
```
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /selfies/{userId}/{allPaths=**} {
      allow read: if true;   // public selfie URLs needed for generation
      allow write: if false; // only server writes
    }
  }
}
```

### Step 3 — Local Development

```bash
# Clone & install
git clone <your-repo>
cd fotofyai
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your BOT_TOKEN and Firebase credentials

# Run locally (polling mode — no webhook needed)
python run_local.py
```

### Step 4 — Deploy to Vercel

#### 4a. Prepare Firebase credentials for Vercel

Since Vercel can't read files, encode your Firebase credentials as a JSON string:

```bash
# On Linux/Mac:
cat firebase-credentials.json | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)))"
```

Copy the output — you'll paste it as an environment variable.

#### 4b. Deploy

```bash
# Install Vercel CLI
npm i -g vercel

# Login and deploy
vercel login
vercel --prod
```

Or push to GitHub and connect on [vercel.com/dashboard](https://vercel.com/dashboard).

#### 4c. Set Environment Variables in Vercel

In your Vercel dashboard → Settings → Environment Variables, add:

| Variable | Value |
|---|---|
| `BOT_TOKEN` | Your Telegram bot token |
| `FIREBASE_CREDENTIALS_JSON` | The JSON string from step 4a |
| `FIREBASE_PROJECT_ID` | Your Firebase project ID |
| `FIREBASE_STORAGE_BUCKET` | `your-project.appspot.com` |
| `WEBHOOK_URL` | `https://your-app.vercel.app` |
| `WEBHOOK_SECRET` | Any random string (e.g. `mysecret123`) |

#### 4d. Register the Webhook

After deploying, visit this URL **once** in your browser:

```
https://your-app.vercel.app/api/setup
```

This registers the webhook with Telegram and sets the bot command menu. You should see:
```json
{"ok": true, "webhook_url": "https://your-app.vercel.app/api/webhook", ...}
```

Your bot is now **live**! 🎉

---

## ⭐ Telegram Stars Payments

To enable paid upgrades:

1. In BotFather → `/mybots` → Select your bot → **Payments**
2. For testing: connect to **Telegram Payments Test** provider
3. For production: works natively with Telegram Stars (`XTR`) — no extra setup needed

### Pricing Tiers

| Package | Credits | Stars | ~USD |
|---|---|---|---|
| Starter Pack | 50 credits | ⭐ 99 | ~$1.3 |
| Pro Pack | 200 credits | ⭐ 299 | ~$3.9 |
| Unlimited Month | ∞ (30 days) | ⭐ 499 | ~$6.5 |

> Edit prices in `bot/config.py` → `PACKAGES` list.

---

## 🎨 Style Presets

Edit or add styles in `bot/config.py` → `STYLE_PRESETS` dict:

```python
STYLE_PRESETS = {
    "🌸 Anime":        "anime style portrait, vibrant colors...",
    "🤖 Cyberpunk":    "cyberpunk portrait, neon lights...",
    "🧝 Fantasy":      "epic fantasy portrait, magical aura...",
    # Add your own...
}
```

---

## 🔧 Admin CLI

```bash
# View bot statistics
python admin.py stats

# Gift credits to a user
python admin.py gift 123456789 50

# View user profile
python admin.py userinfo 123456789
```

---

## 📊 Firestore Collections

| Collection | Purpose |
|---|---|
| `users` | User profiles, credits, state, selfie URL |
| `credit_transactions` | Full audit log of all credit changes |
| `generations` | History of all generated images |

---

## 🐛 Troubleshooting

**Bot not responding?**
- Check webhook is registered: `GET /api/setup`
- Check Vercel function logs in your dashboard
- Verify `BOT_TOKEN` env var is correct

**Image generation failing?**
- Pollinations.ai may occasionally be slow — credit is auto-refunded on timeout
- Try with a simpler prompt first

**Firebase errors?**
- Ensure Firestore is enabled (not just Realtime Database)
- Check `FIREBASE_CREDENTIALS_JSON` is a valid single-line JSON string

**Vercel timeout?**
- Free plan has 10s timeout — upgrade to Vercel Hobby/Pro for 60s
- Set `maxDuration: 60` is already in `vercel.json`

---

## 📄 License

MIT — use freely, modify freely.

---

*Built with ❤️ using Python, aiogram, Pollinations.ai, Firebase & Vercel*
