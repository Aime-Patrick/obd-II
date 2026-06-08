"""
Retrain job orchestrator — production "training worker" equivalent.

Phase 2: quality gates, metric comparison, rollback, MongoDB audit log.
"""

from __future__ import annotations

import asyncio
import os
import sys
import subprocess
from datetime import datetime, timezone
from typing import Any

from config.database import db
from config.settings import settings
from services import ml_model
from services import system_settings_service

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
COLLECT_SCRIPT = os.path.join(_BASE_DIR, "ml", "collect_real_data.py")

_status: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "log": "",
    "labeled_samples": None,
    "real_samples_used": None,
    "model_version": None,
    "metrics": None,
    "previous_metrics": None,
    "promoted": None,
    "rejection_reason": None,
}


def get_status() -> dict[str, Any]:
    return dict(_status)


def is_running() -> bool:
    return _status.get("status") == "running"


def _resolve_python() -> str:
    venv_python = os.path.join(_BASE_DIR, "venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = os.path.join(_BASE_DIR, "venv", "bin", "python")
    if not os.path.exists(venv_python):
        venv_python = sys.executable
    return venv_python


def _parse_labeled_count(log: str) -> int | None:
    for line in log.splitlines():
        if line.startswith("Exported ") and " labeled diagnostics" in line:
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                pass
    return None


def _run_collect_pipeline() -> subprocess.CompletedProcess[str]:
    python = _resolve_python()
    return subprocess.run(
        [python, COLLECT_SCRIPT],
        capture_output=True,
        text=True,
        cwd=_BASE_DIR,
    )


async def validate_retrain_eligibility() -> tuple[bool, str, dict[str, Any]]:
    """Pre-flight checks before starting a retrain job."""
    if db.client is None:
        return False, "Database not connected.", {}

    database = db.client[settings.DATABASE_NAME]
    retrain_cfg = await system_settings_service.get_retrain_settings(database)
    labeled = await database.diagnostics.count_documents({"user_label": {"$exists": True}})
    confirmed_fault = await database.diagnostics.count_documents({"user_label": True})
    confirmed_healthy = await database.diagnostics.count_documents({"user_label": False})

    min_labeled = retrain_cfg["min_labeled_samples"]
    min_per_class = retrain_cfg["min_labels_per_class"]

    summary = {
        "labeled": labeled,
        "confirmed_fault": confirmed_fault,
        "confirmed_healthy": confirmed_healthy,
        "min_labeled_required": min_labeled,
        "min_per_class_required": min_per_class,
    }

    if labeled < min_labeled:
        return (
            False,
            f"Need at least {min_labeled} labeled diagnostics (currently {labeled}).",
            summary,
        )

    if confirmed_fault < min_per_class:
        return (
            False,
            f"Need at least {min_per_class} confirmed-fault labels "
            f"(currently {confirmed_fault}).",
            summary,
        )

    if confirmed_healthy < min_per_class:
        return (
            False,
            f"Need at least {min_per_class} confirmed-healthy labels "
            f"(currently {confirmed_healthy}).",
            summary,
        )

    return True, "Eligible for retraining.", summary


async def _persist_audit(record: dict[str, Any]) -> None:
    if db.client is None:
        return
    database = db.client[settings.DATABASE_NAME]
    await database.retrain_history.insert_one(record)


async def execute_retrain(trigger: str = "admin_api") -> None:
    """Background job: backup → export → train → gate → promote or rollback."""
    global _status

    started_at = datetime.now(timezone.utc)
    previous_metrics = ml_model.read_metrics_file()

    _status = {
        "status": "running",
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "log": "",
        "labeled_samples": None,
        "real_samples_used": None,
        "model_version": None,
        "metrics": None,
        "previous_metrics": previous_metrics,
        "promoted": None,
        "rejection_reason": None,
        "trigger": trigger,
    }

    audit: dict[str, Any] = {
        "started_at": started_at,
        "previous_metrics": previous_metrics,
        "trigger": trigger,
    }

    try:
        ml_model.backup_production_artifacts()

        result = await asyncio.to_thread(_run_collect_pipeline)
        log = (result.stdout or "") + (result.stderr or "")
        _status["log"] = log
        labeled_count = _parse_labeled_count(log)
        _status["labeled_samples"] = labeled_count
        _status["real_samples_used"] = labeled_count
        audit["labeled_samples"] = labeled_count
        audit["log_excerpt"] = log[-4000:] if log else ""

        if result.returncode != 0:
            _status["status"] = "error"
            audit["status"] = "error"
            audit["rejection_reason"] = "Training script failed."
            return

        new_metrics = ml_model.read_metrics_file()
        if not new_metrics:
            ml_model.restore_previous_artifacts()
            _status["status"] = "error"
            _status["rejection_reason"] = "Training finished but metrics file missing."
            audit["status"] = "error"
            audit["rejection_reason"] = _status["rejection_reason"]
            return

        retrain_cfg = await system_settings_service.get_retrain_settings(
            db.client[settings.DATABASE_NAME]
        )
        promote, reason = ml_model.is_better_model(
            new_metrics,
            previous_metrics,
            tolerance=retrain_cfg["metric_tolerance"],
        )
        _status["metrics"] = new_metrics
        audit["new_metrics"] = new_metrics

        if not promote:
            ml_model.restore_previous_artifacts()
            _status["status"] = "rejected"
            _status["promoted"] = False
            _status["rejection_reason"] = reason
            audit["status"] = "rejected"
            audit["promoted"] = False
            audit["rejection_reason"] = reason
            return

        info = ml_model.reload()
        _status["status"] = "success"
        _status["promoted"] = True
        _status["rejection_reason"] = None
        _status["model_version"] = info.get("model_version")
        audit["status"] = "success"
        audit["promoted"] = True
        audit["promotion_reason"] = reason
        audit["model_version"] = info.get("model_version")

    except Exception as exc:
        _status["status"] = "error"
        _status["log"] = (_status.get("log") or "") + f"\n{exc}"
        _status["rejection_reason"] = str(exc)
        audit["status"] = "error"
        audit["rejection_reason"] = str(exc)
        try:
            ml_model.restore_previous_artifacts()
        except Exception:
            pass
    finally:
        finished_at = datetime.now(timezone.utc)
        _status["finished_at"] = finished_at.isoformat()
        audit["finished_at"] = finished_at
        audit["duration_seconds"] = (finished_at - started_at).total_seconds()
        await _persist_audit(audit)


async def rollback_to_previous() -> dict[str, Any]:
    """Manual rollback to last backed-up production model."""
    if not ml_model.has_previous_artifacts():
        return {"success": False, "message": "No previous model backup available."}

    previous_metrics = ml_model.read_metrics_file(ml_model.PREVIOUS_METRICS_PATH)
    ml_model.restore_previous_artifacts()
    info = ml_model.get_info()

    record = {
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "status": "rollback",
        "promoted": True,
        "trigger": "admin_rollback",
        "previous_metrics": ml_model.read_metrics_file(),
        "restored_metrics": previous_metrics,
        "model_version": info.get("model_version"),
    }
    await _persist_audit(record)

    return {
        "success": True,
        "message": "Rolled back to previous model.",
        "model": info,
    }


async def get_retrain_history(limit: int = 20) -> list[dict[str, Any]]:
    if db.client is None:
        return []
    database = db.client[settings.DATABASE_NAME]
    cursor = database.retrain_history.find().sort("started_at", -1).limit(limit)
    rows = await cursor.to_list(length=limit)
    for row in rows:
        row["id"] = str(row.pop("_id"))
        for key in ("started_at", "finished_at"):
            if key in row and row[key] is not None:
                row[key] = row[key].isoformat()
    return rows
