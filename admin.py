"""
Admin utility — run from CLI to manage the bot.
Usage:
  python admin.py stats
  python admin.py gift <telegram_id> <credits>
  python admin.py userinfo <telegram_id>
"""

import sys
import asyncio
from bot.services import firebase as db


def cmd_stats():
    """Show basic bot statistics."""
    firedb = db.get_db()

    users = list(firedb.collection("users").stream())
    total_users = len(users)
    premium_users = sum(1 for u in users if u.to_dict().get("is_premium"))
    total_generated = sum(u.to_dict().get("total_generated", 0) for u in users)
    zero_credit_users = sum(1 for u in users if u.to_dict().get("credits", 0) <= 0)

    print("=" * 40)
    print("📊 FOTOFY AI — BOT STATS")
    print("=" * 40)
    print(f"Total users:       {total_users}")
    print(f"Premium users:     {premium_users}")
    print(f"Total generated:   {total_generated} images")
    print(f"Zero-credit users: {zero_credit_users}")
    print("=" * 40)


def cmd_gift(telegram_id: int, credits: int):
    """Gift credits to a user."""
    user = db.get_user(telegram_id)
    if not user:
        print(f"❌ User {telegram_id} not found.")
        return
    db.add_credits(telegram_id, credits, "admin_gift")
    print(f"✅ Gifted {credits} credits to user {telegram_id} ({user.get('first_name', 'Unknown')})")


def cmd_userinfo(telegram_id: int):
    """Print user profile."""
    user = db.get_user(telegram_id)
    if not user:
        print(f"❌ User {telegram_id} not found.")
        return
    print("=" * 40)
    print(f"👤 USER INFO — {telegram_id}")
    print("=" * 40)
    for key, value in user.items():
        print(f"  {key:25s}: {value}")
    print("=" * 40)


def main():
    if len(sys.argv) < 2:
        print("Usage: python admin.py [stats | gift <id> <credits> | userinfo <id>]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "stats":
        cmd_stats()
    elif cmd == "gift" and len(sys.argv) == 4:
        cmd_gift(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "userinfo" and len(sys.argv) == 3:
        cmd_userinfo(int(sys.argv[2]))
    else:
        print("Unknown command or missing arguments.")
        sys.exit(1)


if __name__ == "__main__":
    main()
