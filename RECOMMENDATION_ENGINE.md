# Enhanced Prediction API with Recommendation Engine

## Overview
The backend now includes an intelligent recommendation engine that analyzes sensor data and provides actionable insights, warnings, and maintenance recommendations.

## New Features

### 1. Sensor Analysis
- Detects abnormal sensor readings
- Categorizes issues by severity (CRITICAL, WARNING, CAUTION)
- Compares values against normal ranges

### 2. Smart Recommendations
- Priority-based recommendations (CRITICAL, HIGH, MEDIUM, LOW)
- Category classification (Engine, Fuel, Air, Throttle, General)
- Actionable steps for each issue
- Cost estimates for repairs

### 3. Predictive Warnings
- Early detection of potential issues
- Trend-based alerts (future enhancement)

## API Response Structure

```json
{
  "has_fault": true,
  "confidence": 0.87,
  "status": "Fault Detected",
  "severity": "CRITICAL",
  "analysis": {
    "abnormal_sensors": [
      {
        "name": "ENGINE_COOLANT_TEMP",
        "value": 110,
        "unit": "°C",
        "normal_range": "85-95",
        "status": "critical",
        "severity": "CRITICAL"
      }
    ],
    "recommendations": [
      {
        "priority": "CRITICAL",
        "category": "ENGINE",
        "message": "Stop vehicle immediately - Engine overheating detected",
        "action": "Turn off engine and check for leaks",
        "estimated_cost": "$50-$200",
        "sensor": "ENGINE_COOLANT_TEMP",
        "current_value": "110 °C"
      }
    ],
    "warnings": []
  }
}
```

## Request Format

```json
{
  "sensors": {
    "ENGINE_COOLANT_TEMP": 110,
    "ENGINE_LOAD": 85,
    "ENGINE_RPM": 2200,
    "FUEL_PRESSURE": 48
  },
  "mark": "toyota",
  "model_name": "corolla",
  "include_recommendations": true
}
```

## Severity Levels

- **CRITICAL** (confidence > 0.85): Immediate action required
- **WARNING** (confidence 0.65-0.85): Attention needed soon
- **CAUTION** (confidence 0.50-0.65): Monitor closely
- **HEALTHY** (no fault): All systems normal

## Monitored Sensors

1. **ENGINE_COOLANT_TEMP** - Engine temperature
2. **ENGINE_LOAD** - Engine load percentage
3. **ENGINE_RPM** - Engine revolutions per minute
4. **FUEL_PRESSURE** - Fuel system pressure
5. **MAF** - Mass airflow sensor
6. **INTAKE_MANIFOLD_PRESSURE** - Intake pressure
7. **THROTTLE_POS** - Throttle position
8. **SPEED** - Vehicle speed
9. **AIR_INTAKE_TEMP** - Air intake temperature
10. **AMBIENT_AIR_TEMP** - Ambient temperature

## Testing

Run the test script:
```bash
python test_recommendations.py
```

Make sure the backend server is running:
```bash
python main.py
```

## Configuration

Edit `rules/fault_rules.json` to customize:
- Normal ranges for sensors
- Warning thresholds
- Critical thresholds
- Recommendation messages
- Cost estimates

## Future Enhancements

1. **Trend Analysis**: Historical data pattern detection
2. **Maintenance Scheduling**: Predictive maintenance based on usage
3. **Multi-Model Classification**: Specific fault type identification
4. **Learning System**: Improve recommendations based on user feedback
