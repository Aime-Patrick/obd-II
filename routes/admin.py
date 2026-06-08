"""
Admin dashboard API routes.
Requires X-Admin-API-Key when ADMIN_API_KEY is set in environment.
"""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from auth.admin_auth import verify_admin_access, get_admin_key_id
from config.database import get_database
from datetime import datetime, timedelta
from collections import defaultdict
from pydantic import BaseModel, Field
from services import retrain_service, ml_model, admin_key_service, system_settings_service

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_access)],
)


# ── 1. Overview stats ─────────────────────────────────────────────────────────

@router.get("/stats")
async def get_overview_stats(db=Depends(get_database)):
    """Total diagnostics, fault rate, active users, registered vehicles."""
    total_diagnostics = await db.diagnostics.count_documents({})
    total_faults      = await db.diagnostics.count_documents({"has_fault": True})
    total_users       = await db.users.count_documents({})
    total_vehicles    = await db.vehicles.count_documents({})
    labeled_count     = await db.diagnostics.count_documents({"user_label": {"$exists": True}})

    fault_rate = round((total_faults / total_diagnostics * 100), 1) if total_diagnostics else 0.0

    return {
        "total_diagnostics": total_diagnostics,
        "total_faults": total_faults,
        "fault_rate_pct": fault_rate,
        "total_users": total_users,
        "total_vehicles": total_vehicles,
        "labeled_samples": labeled_count,
    }


# ── 2. Fault trend (daily counts for last 30 days) ────────────────────────────

@router.get("/trends/faults")
async def get_fault_trends(db=Depends(get_database)):
    """Daily fault vs healthy counts for the last 30 days."""
    since = datetime.utcnow() - timedelta(days=30)

    pipeline = [
        {"$match": {"timestamp": {"$gte": since}}},
        {
            "$group": {
                "_id": {
                    "date": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                    },
                    "has_fault": "$has_fault",
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.date": 1}},
    ]

    results = await db.diagnostics.aggregate(pipeline).to_list(None)

    by_date: dict = defaultdict(lambda: {"faults": 0, "healthy": 0})
    for r in results:
        date = r["_id"]["date"]
        if r["_id"]["has_fault"]:
            by_date[date]["faults"] += r["count"]
        else:
            by_date[date]["healthy"] += r["count"]

    trend = [
        {"date": d, "faults": v["faults"], "healthy": v["healthy"]}
        for d, v in sorted(by_date.items())
    ]
    return {"trend": trend}


# ── 2b. User labels per week (last 12 weeks) ──────────────────────────────────

@router.get("/trends/labels")
async def get_label_trends(db=Depends(get_database)):
    """Weekly count of user-confirmed fault vs healthy labels."""
    since = datetime.utcnow() - timedelta(weeks=12)

    pipeline = [
        {
            "$match": {
                "labeled_at": {"$gte": since},
                "user_label": {"$exists": True},
            }
        },
        {
            "$group": {
                "_id": {
                    "week": {
                        "$dateToString": {
                            "format": "%G-W%V",
                            "date": "$labeled_at",
                        }
                    },
                    "user_label": "$user_label",
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.week": 1}},
    ]

    results = await db.diagnostics.aggregate(pipeline).to_list(None)

    by_week: dict = defaultdict(lambda: {"fault": 0, "healthy": 0})
    for r in results:
        week = r["_id"]["week"]
        if r["_id"]["user_label"]:
            by_week[week]["fault"] += r["count"]
        else:
            by_week[week]["healthy"] += r["count"]

    trend = [
        {"week": w, "fault": v["fault"], "healthy": v["healthy"]}
        for w, v in sorted(by_week.items())
    ]
    return {"trend": trend}


# ── 3. Severity breakdown ─────────────────────────────────────────────────────

@router.get("/trends/severity")
async def get_severity_breakdown(db=Depends(get_database)):
    """Count of diagnostics per severity level (all time)."""
    pipeline = [
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = await db.diagnostics.aggregate(pipeline).to_list(None)
    return {
        "severity": [
            {"severity": r["_id"] or "UNKNOWN", "count": r["count"]}
            for r in results
        ]
    }


# ── 4. Sensor heatmap ────────────────────────────────────────────────────────

@router.get("/sensors/heatmap")
async def get_sensor_heatmap(db=Depends(get_database)):
    pipeline = [
        {"$match": {"has_fault": True, "analysis.sensor_analysis": {"$exists": True}}},
        {"$unwind": "$analysis.sensor_analysis"},
        {
            "$match": {
                "analysis.sensor_analysis.status": {"$in": ["critical", "warning"]}
            }
        },
        {
            "$group": {
                "_id": "$analysis.sensor_analysis.sensor",
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]
    results = await db.diagnostics.aggregate(pipeline).to_list(None)

    if not results:
        fault_docs = await db.diagnostics.find(
            {"has_fault": True}, {"sensor_data": 1}
        ).limit(500).to_list(500)

        sensor_counts: dict = defaultdict(int)
        for doc in fault_docs:
            for key in doc.get("sensor_data", {}).keys():
                sensor_counts[key] += 1

        results = [
            {"_id": k, "count": v}
            for k, v in sorted(sensor_counts.items(), key=lambda x: -x[1])[:15]
        ]

    return {
        "heatmap": [
            {"sensor": r["_id"], "count": r["count"]}
            for r in results
        ]
    }


# ── 5. Labeled data summary ───────────────────────────────────────────────────

@router.get("/labels/summary")
async def get_label_summary(db=Depends(get_database)):
    total      = await db.diagnostics.count_documents({})
    labeled    = await db.diagnostics.count_documents({"user_label": {"$exists": True}})
    confirmed_fault   = await db.diagnostics.count_documents({"user_label": True})
    confirmed_healthy = await db.diagnostics.count_documents({"user_label": False})
    unlabeled  = total - labeled
    retrain_cfg = await system_settings_service.get_retrain_settings(db)

    min_labeled = retrain_cfg["min_labeled_samples"]
    min_per_class = retrain_cfg["min_labels_per_class"]

    return {
        "total": total,
        "labeled": labeled,
        "unlabeled": unlabeled,
        "confirmed_fault": confirmed_fault,
        "confirmed_healthy": confirmed_healthy,
        "label_coverage_pct": round(labeled / total * 100, 1) if total else 0.0,
        "min_labeled_required": min_labeled,
        "min_per_class_required": min_per_class,
        "retrain_eligible": (
            labeled >= min_labeled
            and confirmed_fault >= min_per_class
            and confirmed_healthy >= min_per_class
        ),
    }


# ── 6. Model info ─────────────────────────────────────────────────────────────

@router.get("/model")
async def get_model_info():
    return ml_model.get_info()


# ── 7. Retrain ────────────────────────────────────────────────────────────────

@router.get("/retrain/eligibility")
async def get_retrain_eligibility():
    ok, message, summary = await retrain_service.validate_retrain_eligibility()
    return {"eligible": ok, "message": message, **summary}


@router.post("/retrain")
async def trigger_retrain(background_tasks: BackgroundTasks):
    if retrain_service.is_running():
        raise HTTPException(status_code=409, detail="Retraining already in progress.")

    ok, message, _ = await retrain_service.validate_retrain_eligibility()
    if not ok:
        raise HTTPException(status_code=422, detail=message)

    background_tasks.add_task(retrain_service.execute_retrain)
    return {
        "message": "Retraining started in background. Check /admin/retrain/status for updates.",
        "status": "running",
    }


@router.get("/retrain/status")
async def get_retrain_status():
    return retrain_service.get_status()


@router.get("/retrain/history")
async def get_retrain_history(limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    history = await retrain_service.get_retrain_history(limit=limit)
    return {"history": history}


@router.post("/retrain/rollback")
async def rollback_model():
    if retrain_service.is_running():
        raise HTTPException(status_code=409, detail="Cannot rollback while retraining.")
    result = await retrain_service.rollback_to_previous()
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ── 8. Admin API keys (DB-backed, expiring) ───────────────────────────────────

class CreateAdminKeyBody(BaseModel):
    label: str = Field(default="Admin dashboard", max_length=120)
    expires_in_days: int = Field(default=90, ge=1, le=3650)


class RetrainSettingsBody(BaseModel):
    min_labeled_samples: int = Field(ge=1, le=100000)
    min_labels_per_class: int = Field(ge=1, le=100000)
    metric_tolerance: float = Field(ge=0, le=0.5)
    schedule_enabled: bool | None = None
    schedule_interval_days: int | None = Field(default=None, ge=1, le=90)


def _serialize_retrain_settings(cfg: dict) -> dict:
    out = dict(cfg)
    for key in ("updated_at", "last_scheduled_retrain_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


@router.get("/keys")
async def list_admin_keys(db=Depends(get_database)):
    return {"keys": await admin_key_service.list_keys(db)}


@router.post("/keys")
async def create_admin_key(
    body: CreateAdminKeyBody,
    request: Request,
    db=Depends(get_database),
):
    plain, meta = await admin_key_service.create_key(
        db,
        label=body.label,
        expires_in_days=body.expires_in_days,
        created_by_key_id=get_admin_key_id(request),
    )
    return {
        "message": "Save this key now — it will not be shown again.",
        "plain_key": plain,
        "key": meta,
    }


@router.post("/keys/{key_id}/revoke")
async def revoke_admin_key(key_id: str, db=Depends(get_database)):
    key = await admin_key_service.revoke_key(db, key_id)
    return {"message": "Key revoked.", "key": key}


@router.post("/keys/{key_id}/regenerate")
async def regenerate_admin_key(
    key_id: str,
    request: Request,
    db=Depends(get_database),
    expires_in_days: int = 90,
):
    if expires_in_days < 1 or expires_in_days > 3650:
        raise HTTPException(status_code=422, detail="expires_in_days out of range.")
    plain, meta = await admin_key_service.regenerate_key(
        db,
        key_id,
        expires_in_days=expires_in_days,
        created_by_key_id=get_admin_key_id(request),
    )
    return {
        "message": "Old key revoked. Save the new key now — it will not be shown again.",
        "plain_key": plain,
        "key": meta,
    }


# ── 9. Runtime retrain settings (DB-backed) ───────────────────────────────────

@router.get("/settings/retrain")
async def get_retrain_settings(db=Depends(get_database)):
    cfg = await system_settings_service.get_retrain_settings(db)
    return _serialize_retrain_settings(cfg)


@router.patch("/settings/retrain")
async def update_retrain_settings(
    body: RetrainSettingsBody,
    request: Request,
    db=Depends(get_database),
):
    cfg = await system_settings_service.update_retrain_settings(
        db,
        min_labeled_samples=body.min_labeled_samples,
        min_labels_per_class=body.min_labels_per_class,
        metric_tolerance=body.metric_tolerance,
        schedule_enabled=body.schedule_enabled,
        schedule_interval_days=body.schedule_interval_days,
        updated_by_key_id=get_admin_key_id(request),
    )
    return _serialize_retrain_settings(cfg)

