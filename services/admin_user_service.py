"""Admin user accounts for dashboard login."""

from __future__ import annotations

from datetime import datetime, timezone

from auth.password_utils import hash_password, verify_password
from config.settings import settings


async def ensure_admin_user(db) -> None:
    """Create default admin from env if collection is empty."""
    count = await db.admin_users.count_documents({})
    if count > 0:
        return

    email = settings.ADMIN_EMAIL.strip().lower()
    password = settings.ADMIN_PASSWORD.strip()
    if not email or not password:
        print("WARNING: No admin user in DB and ADMIN_EMAIL/ADMIN_PASSWORD not set.")
        return

    await db.admin_users.insert_one(
        {
            "email": email,
            "password_hash": hash_password(password),
            "full_name": settings.ADMIN_FULL_NAME,
            "role": "admin",
            "created_at": datetime.now(timezone.utc),
        }
    )
    print(f"Seeded admin user: {email}")


async def authenticate_admin(db, email: str, password: str) -> dict | None:
    doc = await db.admin_users.find_one({"email": email.strip().lower()})
    if not doc:
        return None
    if not verify_password(password, doc["password_hash"]):
        return None
    return doc
