"""Runtime retrain thresholds — DB-backed with env fallbacks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.settings import settings

SETTINGS_ID = "retrain"


def _defaults() -> dict[str, Any]:
    return {
        "min_labeled_samples": settings.MIN_LABELED_SAMPLES,
        "min_labels_per_class": settings.MIN_LABELS_PER_CLASS,
        "metric_tolerance": settings.METRIC_TOLERANCE,
        "schedule_enabled": settings.SCHEDULE_RETRAIN_ENABLED,
        "schedule_interval_days": settings.SCHEDULE_RETRAIN_INTERVAL_DAYS,
        "last_scheduled_retrain_at": None,
    }


async def get_retrain_settings(db) -> dict[str, Any]:
    doc = await db.system_settings.find_one({"_id": SETTINGS_ID})
    merged = _defaults()
    if doc:
        merged.update(
            {
                "min_labeled_samples": doc.get(
                    "min_labeled_samples", merged["min_labeled_samples"]
                ),
                "min_labels_per_class": doc.get(
                    "min_labels_per_class", merged["min_labels_per_class"]
                ),
                "metric_tolerance": doc.get(
                    "metric_tolerance", merged["metric_tolerance"]
                ),
                "schedule_enabled": doc.get(
                    "schedule_enabled", merged["schedule_enabled"]
                ),
                "schedule_interval_days": doc.get(
                    "schedule_interval_days", merged["schedule_interval_days"]
                ),
                "last_scheduled_retrain_at": doc.get("last_scheduled_retrain_at"),
                "updated_at": doc.get("updated_at"),
                "updated_by_key_id": doc.get("updated_by_key_id"),
            }
        )
    return merged


async def update_retrain_settings(
    db,
    *,
    min_labeled_samples: int,
    min_labels_per_class: int,
    metric_tolerance: float,
    schedule_enabled: bool | None = None,
    schedule_interval_days: int | None = None,
    updated_by_key_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    existing = await get_retrain_settings(db)
    payload = {
        "_id": SETTINGS_ID,
        "min_labeled_samples": min_labeled_samples,
        "min_labels_per_class": min_labels_per_class,
        "metric_tolerance": metric_tolerance,
        "schedule_enabled": (
            schedule_enabled
            if schedule_enabled is not None
            else existing["schedule_enabled"]
        ),
        "schedule_interval_days": (
            schedule_interval_days
            if schedule_interval_days is not None
            else existing["schedule_interval_days"]
        ),
        "last_scheduled_retrain_at": existing.get("last_scheduled_retrain_at"),
        "updated_at": now,
        "updated_by_key_id": updated_by_key_id,
    }
    await db.system_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": payload},
        upsert=True,
    )
    return await get_retrain_settings(db)


async def record_scheduled_retrain_start(db) -> None:
    now = datetime.now(timezone.utc)
    await db.system_settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {"last_scheduled_retrain_at": now}},
        upsert=True,
    )


async def ensure_defaults(db) -> None:
    existing = await db.system_settings.find_one({"_id": SETTINGS_ID})
    if existing:
        return
    defaults = _defaults()
    await db.system_settings.insert_one(
        {
            "_id": SETTINGS_ID,
            **defaults,
            "last_scheduled_retrain_at": None,
            "updated_at": datetime.now(timezone.utc),
            "updated_by_key_id": None,
        }
    )
