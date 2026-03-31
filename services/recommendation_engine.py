from typing import Dict, List, Any
from .sensor_analyzer import SensorAnalyzer

class RecommendationEngine:
    def __init__(self):
        self.sensor_analyzer = SensorAnalyzer()
    
    def generate_recommendations(
        self, 
        sensor_data: Dict[str, float],
        has_fault: bool,
        confidence: float
    ) -> Dict[str, Any]:
        
        abnormal_sensors = self.sensor_analyzer.analyze_sensors(sensor_data)
        recommendations = []
        warnings = []
        
        # Generate recommendations for abnormal sensors
        for sensor in abnormal_sensors:
            rule = self.sensor_analyzer.get_sensor_rule(sensor["name"])
            
            if sensor["status"] == "critical":
                recommendations.append({
                    "priority": "CRITICAL",
                    "category": self._get_category(sensor["name"]),
                    "message": rule["recommendations"]["critical"],
                    "action": rule["actions"]["critical"],
                    "estimated_cost": rule.get("cost_estimate", "N/A"),
                    "sensor": sensor["name"],
                    "current_value": f"{sensor['value']} {sensor['unit']}"
                })
            elif sensor["status"] == "warning":
                recommendations.append({
                    "priority": "HIGH",
                    "category": self._get_category(sensor["name"]),
                    "message": rule["recommendations"]["warning"],
                    "action": rule["actions"]["warning"],
                    "estimated_cost": rule.get("cost_estimate", "N/A"),
                    "sensor": sensor["name"],
                    "current_value": f"{sensor['value']} {sensor['unit']}"
                })
        
        # Add general fault recommendation if ML detected fault
        if has_fault and confidence > 0.7 and not recommendations:
            recommendations.append({
                "priority": "HIGH" if confidence > 0.85 else "MEDIUM",
                "category": "General",
                "message": "Vehicle fault detected by AI diagnostics",
                "action": "Schedule comprehensive diagnostic inspection",
                "estimated_cost": "$80-$150"
            })
        
        # Add preventive warnings
        if has_fault and confidence < 0.7:
            warnings.append({
                "type": "PREDICTIVE",
                "message": "Potential issue detected with moderate confidence",
                "action": "Monitor vehicle performance closely"
            })
        
        return {
            "abnormal_sensors": abnormal_sensors,
            "recommendations": sorted(recommendations, key=lambda x: self._priority_order(x["priority"])),
            "warnings": warnings
        }
    
    def _get_category(self, sensor_name: str) -> str:
        categories = {
            "ENGINE": ["ENGINE_COOLANT_TEMP", "ENGINE_LOAD", "ENGINE_RPM", "ENGINE_RUNTIME"],
            "FUEL": ["FUEL_PRESSURE", "FUEL_LEVEL", "FUEL_ECONOMY"],
            "AIR": ["MAF", "AIR_INTAKE_TEMP", "INTAKE_MANIFOLD_PRESSURE"],
            "THROTTLE": ["THROTTLE_POS"],
            "GENERAL": ["SPEED", "AMBIENT_AIR_TEMP"]
        }
        
        for category, sensors in categories.items():
            if sensor_name in sensors:
                return category
        return "General"
    
    def _priority_order(self, priority: str) -> int:
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        return order.get(priority, 4)
