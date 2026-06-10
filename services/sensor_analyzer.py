import json
import os
from typing import Dict, List, Any


class SensorAnalyzer:
    def __init__(self):
        rules_path = os.path.join(os.path.dirname(__file__), "..", "rules", "fault_rules.json")
        with open(rules_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)

    def analyze_sensors(self, sensor_data: Dict[str, float]) -> List[Dict[str, Any]]:
        abnormal_sensors = []

        for sensor_name, value in sensor_data.items():
            if sensor_name not in self.rules:
                continue

            rule = self.rules[sensor_name]
            status, severity = self._classify(rule, value)

            if status != "normal":
                normal_min, normal_max = rule["normal_range"]
                abnormal_sensors.append({
                    "name": sensor_name,
                    "value": value,
                    "unit": rule.get("unit", ""),
                    "normal_range": f"{normal_min}-{normal_max}",
                    "status": status,
                    "severity": severity,
                })

        return abnormal_sensors

    def _classify(self, rule: Dict[str, Any], value: float) -> tuple[str, str | None]:
        """
        Order: critical high → critical low → warning band → normal.
        """
        if "critical_threshold" in rule and value >= rule["critical_threshold"]:
            return "critical", "CRITICAL"

        if "critical_low_threshold" in rule and value <= rule["critical_low_threshold"]:
            return "critical", "CRITICAL"

        if "warning_range" in rule:
            warn_min, warn_max = rule["warning_range"]
            if warn_min <= value <= warn_max:
                return "warning", "WARNING"

        if "warning_range_low" in rule:
            low_min, low_max = rule["warning_range_low"]
            if low_min <= value <= low_max:
                return "warning", "WARNING"

        return "normal", None

    def get_sensor_rule(self, sensor_name: str) -> Dict[str, Any]:
        return self.rules.get(sensor_name, {})
