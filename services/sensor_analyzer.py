import json
import os
from typing import Dict, List, Any

class SensorAnalyzer:
    def __init__(self):
        rules_path = os.path.join(os.path.dirname(__file__), "..", "rules", "fault_rules.json")
        with open(rules_path, "r") as f:
            self.rules = json.load(f)
    
    def analyze_sensors(self, sensor_data: Dict[str, float]) -> List[Dict[str, Any]]:
        abnormal_sensors = []
        
        for sensor_name, value in sensor_data.items():
            if sensor_name not in self.rules:
                continue
            
            rule = self.rules[sensor_name]
            normal_min, normal_max = rule["normal_range"]
            
            status = "normal"
            severity = None
            
            if "critical_threshold" in rule:
                if value >= rule["critical_threshold"]:
                    status = "critical"
                    severity = "CRITICAL"
                elif "critical_low_threshold" in rule and value <= rule["critical_low_threshold"]:
                    status = "critical"
                    severity = "CRITICAL"
                elif "warning_range" in rule:
                    warn_min, warn_max = rule["warning_range"]
                    if warn_min <= value <= warn_max:
                        status = "warning"
                        severity = "WARNING"
            
            if status != "normal":
                abnormal_sensors.append({
                    "name": sensor_name,
                    "value": value,
                    "unit": rule.get("unit", ""),
                    "normal_range": f"{normal_min}-{normal_max}",
                    "status": status,
                    "severity": severity
                })
        
        return abnormal_sensors
    
    def get_sensor_rule(self, sensor_name: str) -> Dict[str, Any]:
        return self.rules.get(sensor_name, {})
