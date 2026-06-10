"""Trend-based recommendations from recent diagnostic history."""

from __future__ import annotations

from typing import Any

from .sensor_analyzer import SensorAnalyzer

MIN_HISTORY_POINTS = 3
MAX_HISTORY_SCANS = 8


class TrendAnalyzer:
    def __init__(self) -> None:
        self._analyzer = SensorAnalyzer()

    def generate_trend_recommendations(
        self,
        current_sensors: dict[str, float],
        history: list[dict[str, Any]],
        skip_sensors: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Detect worsening sensor trends across recent scans.

        Skips sensors already flagged abnormal on the current scan.
        """
        skip = skip_sensors or set()
        recommendations: list[dict[str, Any]] = []

        for sensor_name, rule in self._analyzer.rules.items():
            if sensor_name in skip:
                continue
            if sensor_name not in current_sensors:
                continue

            values = self._collect_values(sensor_name, history, current_sensors)
            if len(values) < MIN_HISTORY_POINTS:
                continue

            current_value = float(current_sensors[sensor_name])
            status, _ = self._analyzer._classify(rule, current_value)
            if status != "normal":
                continue

            direction = self._trend_direction(rule)
            if direction is None:
                continue

            recent = values[-MIN_HISTORY_POINTS:]
            if not self._is_worsening(recent, direction):
                continue

            delta = abs(recent[-1] - recent[0])
            if not self._meaningful_delta(sensor_name, rule, delta):
                continue

            unit = rule.get("unit", "")
            message, action = self._trend_copy(sensor_name, direction, delta, unit)

            recommendations.append({
                "priority": "MEDIUM",
                "category": "Trend",
                "message": message,
                "action": action,
                "sensor": sensor_name,
                "current_value": f"{current_value} {unit}".strip(),
                "trend": {
                    "direction": direction,
                    "points": len(recent),
                    "delta": round(delta, 2),
                    "values": [round(v, 2) for v in recent],
                },
            })

        return recommendations

    def _collect_values(
        self,
        sensor_name: str,
        history: list[dict[str, Any]],
        current_sensors: dict[str, float],
    ) -> list[float]:
        values: list[float] = []
        for doc in history[-MAX_HISTORY_SCANS:]:
            data = doc.get("sensor_data") or {}
            if sensor_name in data and data[sensor_name] != 0.0:
                values.append(float(data[sensor_name]))
        if sensor_name in current_sensors and current_sensors[sensor_name] != 0.0:
            values.append(float(current_sensors[sensor_name]))
        return values

    def _trend_direction(self, rule: dict[str, Any]) -> str | None:
        """rising_bad = higher values are worse; falling_bad = lower values are worse."""
        normal_min, normal_max = rule["normal_range"]
        has_high = "critical_threshold" in rule or (
            "warning_range" in rule and rule["warning_range"][0] >= normal_max
        )
        has_low = "critical_low_threshold" in rule or (
            "warning_range" in rule and rule["warning_range"][1] <= normal_min
        )

        if has_high and has_low:
            return "either_bad"
        if has_high:
            return "rising_bad"
        if has_low:
            return "falling_bad"
        return None

    def _is_worsening(self, values: list[float], direction: str) -> bool:
        if direction == "rising_bad":
            return all(values[i] < values[i + 1] for i in range(len(values) - 1))
        if direction == "falling_bad":
            return all(values[i] > values[i + 1] for i in range(len(values) - 1))
        if direction == "either_bad":
            rising = all(values[i] < values[i + 1] for i in range(len(values) - 1))
            falling = all(values[i] > values[i + 1] for i in range(len(values) - 1))
            return rising or falling
        return False

    def _meaningful_delta(
        self, sensor_name: str, rule: dict[str, Any], delta: float
    ) -> bool:
        if "FUEL_TRIM" in sensor_name:
            return delta >= 4.0
        normal_min, normal_max = rule["normal_range"]
        span = max(normal_max - normal_min, 1.0)
        return delta >= span * 0.15

    def _trend_copy(
        self, sensor_name: str, direction: str, delta: float, unit: str
    ) -> tuple[str, str]:
        label = sensor_name.replace("_", " ").title()
        if direction == "rising_bad":
            return (
                f"{label} is trending upward over recent scans (+{delta:.1f} {unit})".strip(),
                "Monitor on your next drives; if the trend continues, inspect before it becomes critical",
            )
        if direction == "falling_bad":
            return (
                f"{label} is trending downward over recent scans (-{delta:.1f} {unit})".strip(),
                "Monitor on your next drives; if the trend continues, inspect before it becomes critical",
            )
        return (
            f"{label} is drifting out of its usual range over recent scans",
            "Monitor closely and re-scan after driving; schedule inspection if the pattern continues",
        )
