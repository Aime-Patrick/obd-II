from typing import Dict, List, Any

from .sensor_analyzer import SensorAnalyzer


class RecommendationEngine:
    def __init__(self):
        self.sensor_analyzer = SensorAnalyzer()

    def generate_recommendations(
        self,
        sensor_data: Dict[str, float],
        has_fault: bool,
        confidence: float,
        abnormal_sensors: List[Dict[str, Any]] | None = None,
        trend_recommendations: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        if abnormal_sensors is None:
            abnormal_sensors = self.sensor_analyzer.analyze_sensors(sensor_data)

        recommendations: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for sensor in abnormal_sensors:
            rule = self.sensor_analyzer.get_sensor_rule(sensor["name"])
            if not rule:
                continue

            if sensor["status"] == "critical":
                recommendations.append({
                    "priority": "CRITICAL",
                    "category": self._get_category(sensor["name"]),
                    "message": rule["recommendations"]["critical"],
                    "action": rule["actions"]["critical"],
                    "sensor": sensor["name"],
                    "current_value": f"{sensor['value']} {sensor['unit']}",
                })
            elif sensor["status"] == "warning":
                recommendations.append({
                    "priority": "HIGH",
                    "category": self._get_category(sensor["name"]),
                    "message": rule["recommendations"]["warning"],
                    "action": rule["actions"]["warning"],
                    "sensor": sensor["name"],
                    "current_value": f"{sensor['value']} {sensor['unit']}",
                })

        if has_fault and confidence > 0.7 and not recommendations:
            recommendations.append({
                "priority": "HIGH" if confidence > 0.85 else "MEDIUM",
                "category": "General",
                "message": "Vehicle fault detected by AI diagnostics",
                "action": "Schedule a comprehensive diagnostic inspection with a qualified mechanic",
            })

        if has_fault and confidence < 0.7:
            warnings.append({
                "type": "PREDICTIVE",
                "message": "Potential issue detected with moderate confidence",
                "action": "Monitor vehicle performance closely and re-scan after driving",
            })

        for warning in warnings:
            recommendations.append({
                "priority": "MEDIUM",
                "category": "Predictive",
                "message": warning["message"],
                "action": warning["action"],
            })

        if trend_recommendations:
            recommendations.extend(trend_recommendations)

        return {
            "abnormal_sensors": abnormal_sensors,
            "recommendations": sorted(
                recommendations, key=lambda x: self._priority_order(x["priority"])
            ),
            "warnings": warnings,
        }

    def _get_category(self, sensor_name: str) -> str:
        categories = {
            "ENGINE": [
                "ENGINE_COOLANT_TEMP",
                "ENGINE_LOAD",
                "ENGINE_RPM",
                "ENGINE_RUNTIME",
            ],
            "FUEL": [
                "FUEL_PRESSURE",
                "FUEL_LEVEL",
                "FUEL_ECONOMY",
                "SHORT_TERM_FUEL_TRIM_BANK_1",
                "LONG_TERM_FUEL_TRIM_BANK_1",
                "SHORT_TERM_FUEL_TRIM_BANK_2",
                "LONG_TERM_FUEL_TRIM_BANK_2",
            ],
            "AIR": ["MAF", "AIR_INTAKE_TEMP", "INTAKE_MANIFOLD_PRESSURE"],
            "THROTTLE": ["THROTTLE_POS"],
            "GENERAL": ["SPEED", "AMBIENT_AIR_TEMP"],
        }

        for category, sensors in categories.items():
            if sensor_name in sensors:
                return category
        return "General"

    def _priority_order(self, priority: str) -> int:
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        return order.get(priority, 4)
