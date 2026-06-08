"""
Model serving layer — production "inference service" equivalent.

Big-company mapping:
  - This module = model registry production pointer + hot swap
  - Training lives in retrain_service.py (separate worker job)
  - Routes only call predict(); they never load joblib directly
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime, timezone
from typing import Any

import joblib
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(_BASE_DIR, "ml", "obd_model.joblib")
METADATA_PATH = os.path.join(_BASE_DIR, "model_metadata.json")
METRICS_PATH = os.path.join(_BASE_DIR, "ml", "training_metrics.json")
PREVIOUS_MODEL_PATH = os.path.join(_BASE_DIR, "ml", "obd_model.previous.joblib")
PREVIOUS_METADATA_PATH = os.path.join(_BASE_DIR, "model_metadata.previous.json")
PREVIOUS_METRICS_PATH = os.path.join(_BASE_DIR, "ml", "training_metrics.previous.json")

_lock = threading.Lock()
_model = None
_metadata: dict[str, Any] | None = None
_loaded_at: str | None = None


def ensure_loaded() -> None:
    """Load model on first use or after reload."""
    global _model, _metadata, _loaded_at
    with _lock:
        if _model is None:
            _model = joblib.load(MODEL_PATH)
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                _metadata = json.load(f)
            _loaded_at = datetime.now(timezone.utc).isoformat()


def read_metrics_file(path: str = METRICS_PATH) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def backup_production_artifacts() -> bool:
    """Snapshot current production model before training (rollback point)."""
    backed_up = False
    for src, dst in (
        (MODEL_PATH, PREVIOUS_MODEL_PATH),
        (METADATA_PATH, PREVIOUS_METADATA_PATH),
        (METRICS_PATH, PREVIOUS_METRICS_PATH),
    ):
        if os.path.exists(src):
            shutil.copy2(src, dst)
            backed_up = True
    return backed_up


def restore_previous_artifacts() -> bool:
    """Restore previous model files and hot-reload."""
    if not os.path.exists(PREVIOUS_MODEL_PATH):
        return False
    for src, dst in (
        (PREVIOUS_MODEL_PATH, MODEL_PATH),
        (PREVIOUS_METADATA_PATH, METADATA_PATH),
        (PREVIOUS_METRICS_PATH, METRICS_PATH),
    ):
        if os.path.exists(src):
            shutil.copy2(src, dst)
    reload()
    return True


def has_previous_artifacts() -> bool:
    return os.path.exists(PREVIOUS_MODEL_PATH)


def is_better_model(
    new_metrics: dict[str, Any],
    old_metrics: dict[str, Any] | None,
    tolerance: float = 0.005,
) -> tuple[bool, str]:
    """
    Quality gate: promote only if new model is not worse than current.
    Primary metric: F1. Tie-breaker: ROC-AUC.
    """
    if not old_metrics:
        return True, "No previous metrics — first promotion."

    new_f1 = float(new_metrics.get("f1", 0))
    old_f1 = float(old_metrics.get("f1", 0))
    new_auc = float(new_metrics.get("roc_auc", 0))
    old_auc = float(old_metrics.get("roc_auc", 0))

    if new_f1 >= old_f1 - tolerance:
        if new_f1 > old_f1 + tolerance:
            return True, f"F1 improved ({old_f1:.4f} → {new_f1:.4f})."
        if new_auc >= old_auc - tolerance:
            return True, f"Metrics acceptable (F1 {new_f1:.4f}, ROC-AUC {new_auc:.4f})."
        return False, (
            f"Rejected: F1 flat but ROC-AUC dropped "
            f"({old_auc:.4f} → {new_auc:.4f})."
        )

    return False, f"Rejected: F1 dropped ({old_f1:.4f} → {new_f1:.4f})."


def reload() -> dict[str, Any]:
    """Hot-swap production model without restarting the server."""
    global _model, _metadata, _loaded_at
    with _lock:
        new_model = joblib.load(MODEL_PATH)
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            new_metadata = json.load(f)
        _model = new_model
        _metadata = new_metadata
        _loaded_at = datetime.now(timezone.utc).isoformat()
    return get_info()


def get_metadata() -> dict[str, Any]:
    ensure_loaded()
    assert _metadata is not None
    return _metadata


def get_feature_order() -> list[str]:
    meta = get_metadata()
    order = meta.get("__feature_order__", list(meta.keys()))
    return [f for f in order if f != "__feature_order__"]


def build_feature_row(sensor_data: dict[str, float]) -> dict[str, float]:
    """Map OBD sensor dict → model feature row (with derived features)."""
    meta = get_metadata()
    feature_order = get_feature_order()

    input_data: dict[str, float] = {}
    for feat in feature_order:
        matched = next(
            (
                v
                for k, v in sensor_data.items()
                if k.upper().strip().replace(" ", "_") == feat
            ),
            None,
        )
        input_data[feat] = float(matched if matched is not None else meta.get(feat, 0.0))

    rpm = input_data.get("ENGINE_RPM", 1)
    load = input_data.get("ENGINE_LOAD", 1)
    temp = input_data.get("ENGINE_COOLANT_TEMP", 0)
    thr = input_data.get("THROTTLE_POS", 0)
    ait = input_data.get("AIR_INTAKE_TEMP", temp)
    stft1 = input_data.get("SHORT_TERM_FUEL_TRIM_BANK_1", 0)
    ltft2 = input_data.get("LONG_TERM_FUEL_TRIM_BANK_2", 0)

    if "RPM_LOAD_RATIO" in feature_order:
        input_data["RPM_LOAD_RATIO"] = rpm / max(load, 1)
    if "TEMP_RPM_RATIO" in feature_order:
        input_data["TEMP_RPM_RATIO"] = temp / max(rpm, 1)
    if "THROTTLE_LOAD_DIFF" in feature_order:
        input_data["THROTTLE_LOAD_DIFF"] = thr - load
    if "FUEL_TRIM_TOTAL" in feature_order:
        input_data["FUEL_TRIM_TOTAL"] = stft1 + ltft2
    if "INTAKE_TEMP_DIFF" in feature_order:
        input_data["INTAKE_TEMP_DIFF"] = temp - ait

    return input_data


def predict_from_sensors(sensor_data: dict[str, float]) -> tuple[bool, float]:
    """Run inference. Returns (has_fault, confidence)."""
    ensure_loaded()
    assert _model is not None

    feature_order = get_feature_order()
    input_data = build_feature_row(sensor_data)
    df_input = pd.DataFrame([input_data])[feature_order]

    prediction = bool(_model.predict(df_input)[0])
    confidence = float(max(_model.predict_proba(df_input)[0]))
    return prediction, confidence


def get_info() -> dict[str, Any]:
    """Model version info for /health and admin dashboards."""
    ensure_loaded()
    meta = get_metadata()
    metrics: dict[str, Any] = read_metrics_file() or {}

    return {
        "model_version": meta.get("__trained_at__"),
        "feature_count": len(get_feature_order()),
        "metrics": metrics or None,
        "loaded_at": _loaded_at,
        "has_previous_model": has_previous_artifacts(),
    }
