"""DB-backed admin API keys with expiry, revoke, and regenerate."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from auth.password_utils import hash_password, verify_password

KEY_PREFIX = "sdx_"
DEFAULT_EXPIRY_DAYS = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    """Normalize MongoDB datetimes (often naive UTC) for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def generate_plain_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def _serialize_key(doc: dict[str, Any]) -> dict[str, Any]:
    expires_at = _as_utc(doc.get("expires_at"))
    return {
        "id": str(doc["_id"]),
        "label": doc.get("label", ""),
        "key_prefix": doc.get("key_prefix", ""),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "revoked_at": doc["revoked_at"].isoformat() if doc.get("revoked_at") else None,
        "last_used_at": doc["last_used_at"].isoformat() if doc.get("last_used_at") else None,
        "is_active": doc.get("revoked_at") is None
        and expires_at is not None
        and expires_at > _now(),
    }


async def create_key(
    db,
    *,
    label: str,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS,
    plain_key: str | None = None,
    created_by_key_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Create a key. Returns (plain_key, public_metadata). Plain key shown once."""
    if expires_in_days < 1 or expires_in_days > 3650:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expires_in_days must be between 1 and 3650.",
        )

    plain = plain_key or generate_plain_key()
    now = _now()
    doc = {
        "key_hash": hash_password(plain),
        "key_prefix": plain[:16],
        "label": label.strip() or "Admin key",
        "created_at": now,
        "expires_at": now + timedelta(days=expires_in_days),
        "revoked_at": None,
        "last_used_at": None,
        "created_by_key_id": created_by_key_id,
    }
    result = await db.admin_api_keys.insert_one(doc)
    doc["_id"] = result.inserted_id
    meta = _serialize_key(doc)
    meta["plain_key"] = plain
    return plain, meta


async def validate_key(db, plain_key: str | None) -> dict[str, Any]:
    if not plain_key or len(plain_key) < 16:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key.",
        )

    prefix = plain_key[:16]
    now = _now()
    candidates = await db.admin_api_keys.find(
        {"key_prefix": prefix, "revoked_at": None},
    ).to_list(10)

    for doc in candidates:
        expires_at = _as_utc(doc.get("expires_at"))
        if expires_at is None or expires_at <= now:
            continue
        if verify_password(plain_key, doc["key_hash"]):
            await db.admin_api_keys.update_one(
                {"_id": doc["_id"]},
                {"$set": {"last_used_at": now}},
            )
            doc["last_used_at"] = now
            return doc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or revoked admin API key.",
    )


async def list_keys(db) -> list[dict[str, Any]]:
    cursor = db.admin_api_keys.find().sort("created_at", -1)
    docs = await cursor.to_list(100)
    return [_serialize_key(d) for d in docs]


async def revoke_key(db, key_id: str) -> dict[str, Any]:
    try:
        oid = ObjectId(key_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Key not found.") from exc

    result = await db.admin_api_keys.update_one(
        {"_id": oid, "revoked_at": None},
        {"$set": {"revoked_at": _now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Key not found or already revoked.")

    doc = await db.admin_api_keys.find_one({"_id": oid})
    return _serialize_key(doc)


async def regenerate_key(
    db,
    key_id: str,
    *,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS,
    created_by_key_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    try:
        oid = ObjectId(key_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Key not found.") from exc

    old = await db.admin_api_keys.find_one({"_id": oid})
    if not old:
        raise HTTPException(status_code=404, detail="Key not found.")

    await db.admin_api_keys.update_one(
        {"_id": oid},
        {"$set": {"revoked_at": _now()}},
    )

    label = old.get("label", "Admin key")
    if not label.endswith("(regenerated)"):
        label = f"{label} (regenerated)"

    return await create_key(
        db,
        label=label,
        expires_in_days=expires_in_days,
        created_by_key_id=created_by_key_id,
    )


async def seed_bootstrap_key(db, plain_key: str, label: str = "Bootstrap key") -> bool:
    """Import env bootstrap key into DB if no keys exist. Returns True if created."""
    count = await db.admin_api_keys.count_documents({})
    if count > 0:
        return False
    await create_key(
        db,
        label=label,
        expires_in_days=365,
        plain_key=plain_key,
        created_by_key_id=None,
    )
    return True


async def seed_dev_key_if_empty(db) -> str | None:
    """Auto-generate a dev key when DB has none and no bootstrap is configured."""
    count = await db.admin_api_keys.count_documents({})
    if count > 0:
        return None
    plain, _ = await create_key(
        db,
        label="Auto-generated dev key",
        expires_in_days=90,
    )
    return plain
