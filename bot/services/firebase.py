"""
Firebase service — Firestore for user/credits data, Storage for selfies.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import firebase_admin
from firebase_admin import credentials, firestore, storage

from bot.config import (
    FIREBASE_CREDENTIALS_PATH,
    FIREBASE_CREDENTIALS_JSON,
    FIREBASE_STORAGE_BUCKET,
    FREE_CREDITS_ON_SIGNUP,
    REFILL_CREDITS,
    REFILL_DAYS,
)

# ── Firebase Initialization ───────────────────────────────────

_initialized = False


def _init_firebase():
    global _initialized
    if _initialized or len(firebase_admin._apps) > 0:
        _initialized = True
        return

    # On Vercel: credentials come as a JSON string env var
    if FIREBASE_CREDENTIALS_JSON:
        cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
    elif os.path.exists(FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    else:
        raise RuntimeError(
            "Firebase credentials not found. Set FIREBASE_CREDENTIALS_JSON "
            "or provide firebase-credentials.json file."
        )

    storage_bucket = FIREBASE_STORAGE_BUCKET or None
    firebase_admin.initialize_app(cred, {"storageBucket": storage_bucket})
    _initialized = True


def get_db() -> firestore.Client:
    _init_firebase()
    return firestore.client()


def get_bucket():
    _init_firebase()
    return storage.bucket()


# ── User Operations ───────────────────────────────────────────


def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Return user document or None if not found."""
    db = get_db()
    doc = db.collection("users").document(str(telegram_id)).get()
    return doc.to_dict() if doc.exists else None


def create_user(
    telegram_id: int, first_name: str, username: Optional[str]
) -> Dict[str, Any]:
    """Create a new user with 20 free credits."""
    db = get_db()
    now = datetime.now(timezone.utc)
    data = {
        "telegram_id": telegram_id,
        "first_name": first_name,
        "username": username or "",
        "credits": FREE_CREDITS_ON_SIGNUP,
        "last_gift_at": now,
        "is_premium": False,
        "premium_expires_at": None,
        "selfie_file_id": None,
        "selfie_url": None,
        "state": "IDLE",
        "state_data": {},
        "created_at": now,
        "total_generated": 0,
    }
    db.collection("users").document(str(telegram_id)).set(data)
    _log_transaction(db, telegram_id, +FREE_CREDITS_ON_SIGNUP, "new_user_gift")
    return data


def get_or_create_user(
    telegram_id: int, first_name: str, username: Optional[str]
) -> Dict[str, Any]:
    user = get_user(telegram_id)
    if user is None:
        user = create_user(telegram_id, first_name, username)
    return user


def update_user(telegram_id: int, data: Dict[str, Any]):
    """Update fields on the user document."""
    db = get_db()
    db.collection("users").document(str(telegram_id)).update(data)


# ── State Management (FSM) ────────────────────────────────────


def get_state(telegram_id: int) -> str:
    user = get_user(telegram_id)
    if user:
        return user.get("state", "IDLE")
    return "IDLE"


def set_state(telegram_id: int, state: str, state_data: Dict[str, Any] = {}):
    update_user(telegram_id, {"state": state, "state_data": state_data})


def get_state_data(telegram_id: int) -> Dict[str, Any]:
    user = get_user(telegram_id)
    if user:
        return user.get("state_data", {})
    return {}


# ── Credit Operations ─────────────────────────────────────────


def deduct_credit(telegram_id: int) -> bool:
    """
    Deduct 1 credit. Returns True if successful, False if no credits.
    Uses Firestore transaction for atomicity.
    """
    db = get_db()
    user_ref = db.collection("users").document(str(telegram_id))

    @firestore.transactional
    def _txn(transaction, ref):
        snapshot = ref.get(transaction=transaction)
        user = snapshot.to_dict()
        credits = user.get("credits", 0)
        is_premium = user.get("is_premium", False)
        premium_expires = user.get("premium_expires_at")

        # Check if premium is still active
        if is_premium and premium_expires:
            now = datetime.now(timezone.utc)
            if hasattr(premium_expires, "tzinfo") and premium_expires.tzinfo:
                if now < premium_expires:
                    # Premium active — no credit deduction
                    transaction.update(ref, {"total_generated": firestore.Increment(1)})
                    return True
            # Premium expired — reset flag
            transaction.update(ref, {"is_premium": False, "premium_expires_at": None})

        if credits <= 0:
            return False

        transaction.update(
            ref,
            {
                "credits": firestore.Increment(-1),
                "total_generated": firestore.Increment(1),
            },
        )
        return True

    txn = db.transaction()
    success = _txn(txn, user_ref)
    if success:
        _log_transaction(db, telegram_id, -1, "image_generation")
    return success


def add_credits(telegram_id: int, amount: int, reason: str):
    """Add credits to a user account."""
    db = get_db()
    update_user(telegram_id, {"credits": firestore.Increment(amount)})
    _log_transaction(db, telegram_id, +amount, reason)


def check_and_refill_credits(telegram_id: int) -> bool:
    """
    Check if user qualifies for free 3-day refill.
    Returns True if credits were gifted.
    """
    user = get_user(telegram_id)
    if not user:
        return False

    if user.get("credits", 0) > 0:
        return False  # Still has credits

    last_gift = user.get("last_gift_at")
    if last_gift is None:
        last_gift = user.get("created_at")

    if last_gift is None:
        return False

    # Handle Firestore Timestamps
    if hasattr(last_gift, "ToDatetime"):
        last_gift = last_gift.ToDatetime(tzinfo=timezone.utc)
    elif not hasattr(last_gift, "tzinfo"):
        last_gift = last_gift.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    delta = now - last_gift

    if delta >= timedelta(days=REFILL_DAYS):
        db = get_db()
        db.collection("users").document(str(telegram_id)).update(
            {
                "credits": REFILL_CREDITS,
                "last_gift_at": now,
            }
        )
        _log_transaction(db, telegram_id, +REFILL_CREDITS, "3day_refill_gift")
        return True

    return False


def time_until_refill(telegram_id: int) -> timedelta:
    """Return how long until the user gets free credits."""
    user = get_user(telegram_id)
    if not user:
        return timedelta(days=REFILL_DAYS)

    last_gift = user.get("last_gift_at") or user.get("created_at")
    if last_gift is None:
        return timedelta(days=REFILL_DAYS)

    if hasattr(last_gift, "ToDatetime"):
        last_gift = last_gift.ToDatetime(tzinfo=timezone.utc)
    elif not hasattr(last_gift, "tzinfo"):
        last_gift = last_gift.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    eligible_at = last_gift + timedelta(days=REFILL_DAYS)
    remaining = eligible_at - now
    return remaining if remaining.total_seconds() > 0 else timedelta(0)


# ── Premium / Purchases ───────────────────────────────────────


def apply_purchase(telegram_id: int, package_id: str, credits: int):
    """Apply a purchase — add credits or set premium."""
    db = get_db()
    now = datetime.now(timezone.utc)

    if package_id == "monthly":
        expires = now + timedelta(days=30)
        db.collection("users").document(str(telegram_id)).update(
            {
                "is_premium": True,
                "premium_expires_at": expires,
                "credits": firestore.Increment(credits),
                "last_gift_at": now,
            }
        )
        _log_transaction(
            db, telegram_id, +credits, f"purchase_{package_id}_subscription"
        )
    else:
        db.collection("users").document(str(telegram_id)).update(
            {
                "credits": firestore.Increment(credits),
            }
        )
        _log_transaction(db, telegram_id, +credits, f"purchase_{package_id}")


# ── Selfie Storage ────────────────────────────────────────────


def save_selfie_info(telegram_id: int, file_id: str, selfie_url: str):
    """Save the user's selfie file_id and public URL."""
    update_user(
        telegram_id,
        {
            "selfie_file_id": file_id,
            "selfie_url": selfie_url,
        },
    )


# ── Generation History ────────────────────────────────────────


def save_generation(telegram_id: int, prompt: str, style: str, image_url: str):
    db = get_db()
    db.collection("generations").add(
        {
            "user_id": str(telegram_id),
            "prompt": prompt,
            "style": style,
            "image_url": image_url,
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_recent_generations(telegram_id: int, limit: int = 5):
    db = get_db()
    docs = (
        db.collection("generations")
        .where("user_id", "==", str(telegram_id))
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [doc.to_dict() for doc in docs]


# ── Internal Helpers ──────────────────────────────────────────


def _log_transaction(db, telegram_id: int, delta: int, reason: str):
    db.collection("credit_transactions").add(
        {
            "user_id": str(telegram_id),
            "delta": delta,
            "reason": reason,
            "created_at": datetime.now(timezone.utc),
        }
    )
