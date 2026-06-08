"""Background scheduler — weekly retrain when new labels exist."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.database import db
from config.settings import settings
from services import retrain_service, system_settings_service

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def maybe_run_scheduled_retrain() -> None:
    """Check gates and start retrain if interval elapsed and new labels exist."""
    if retrain_service.is_running():
        logger.debug("Scheduled retrain skipped: job already running.")
        return

    if db.client is None:
        logger.warning("Scheduled retrain skipped: database not connected.")
        return

    database = db.client[settings.DATABASE_NAME]
    cfg = await system_settings_service.get_retrain_settings(database)

    if not cfg.get("schedule_enabled"):
        return

    now = datetime.now(timezone.utc)
    interval_days = int(cfg.get("schedule_interval_days") or 7)
    last_run = cfg.get("last_scheduled_retrain_at")

    if last_run is not None:
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        elapsed_days = (now - last_run).total_seconds() / 86400
        if elapsed_days < interval_days:
            logger.debug(
                "Scheduled retrain skipped: %.1f days since last run (interval %d).",
                elapsed_days,
                interval_days,
            )
            return

    label_since = last_run or datetime(1970, 1, 1, tzinfo=timezone.utc)
    new_labels = await database.diagnostics.count_documents(
        {
            "labeled_at": {"$gte": label_since},
            "user_label": {"$exists": True},
        }
    )
    if new_labels == 0:
        logger.info("Scheduled retrain skipped: no new labels since last run.")
        return

    ok, message, _ = await retrain_service.validate_retrain_eligibility()
    if not ok:
        logger.info("Scheduled retrain skipped: %s", message)
        return

    logger.info(
        "Starting scheduled retrain (%d new label(s) since last run).",
        new_labels,
    )
    await system_settings_service.record_scheduled_retrain_start(database)
    await retrain_service.execute_retrain(trigger="scheduled")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        maybe_run_scheduled_retrain,
        "cron",
        hour=3,
        minute=0,
        id="scheduled_retrain",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("APScheduler started (scheduled retrain check daily at 03:00 UTC).")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("APScheduler stopped.")
