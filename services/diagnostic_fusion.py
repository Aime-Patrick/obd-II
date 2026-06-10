"""Combine rule-based sensor analysis with ML output into one diagnostic result."""

from __future__ import annotations

from typing import Any


def fuse_signals(
    abnormal_sensors: list[dict[str, Any]],
    ml_prediction: bool,
    ml_confidence: float,
) -> tuple[bool, float, str]:
    """
    Merge rule-based and ML signals into has_fault, confidence, severity.

    Rules take priority for severity when abnormal sensors are present.
    """
    critical_count = sum(1 for s in abnormal_sensors if s["status"] == "critical")
    warning_count = sum(1 for s in abnormal_sensors if s["status"] == "warning")

    if critical_count > 0:
        return True, max(ml_confidence, 0.92), "CRITICAL"
    if warning_count > 0:
        return True, max(ml_confidence, 0.78), "WARNING"
    if ml_prediction and ml_confidence > 0.70:
        return True, ml_confidence, "CAUTION"
    if ml_prediction:
        confidence = ml_confidence if ml_confidence else 0.65
        return True, confidence, "CAUTION"
    confidence = 1.0 - ml_confidence if not ml_prediction else 0.65
    return False, confidence, "HEALTHY"
