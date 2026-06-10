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

### 3. Predictive guidance
- When ML detects a fault with moderate confidence (< 70%) and no rule-based sensor match, a **MEDIUM** priority recommendation is added

### 4. Trend-based guidance
- Compares the last 3–8 diagnostics for the same vehicle
- If a sensor still reads **normal** but values are consistently rising (or falling for low-side sensors), a **Trend** recommendation is added
- Skips sensors already flagged abnormal on the current scan

### Endpoint
- Use **`POST /diagnostics`** only. `POST /predict` returns **410 Gone**.

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
10. **FUEL_LEVEL** - Tank level (%)
11. **AMBIENT_AIR_TEMP** - Ambient temperature
12. **SHORT_TERM_FUEL_TRIM_BANK_1** / **LONG_TERM_FUEL_TRIM_BANK_1**
13. **SHORT_TERM_FUEL_TRIM_BANK_2** / **LONG_TERM_FUEL_TRIM_BANK_2**

Sensors polled without rules yet: `ENGINE_RUNTIME`, `BAROMETRIC_PRESSURE`.

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
- `normal_range`, `warning_range`
- `critical_threshold` (high-side) or `critical_low_threshold` (low-side, e.g. fuel pressure)
- `warning_range_low` for bidirectional sensors (fuel trim)
- `recommendations` and `actions` message text per severity

## Future Enhancements

1. **Trend Analysis**: Historical data pattern detection
2. **Maintenance Scheduling**: Predictive maintenance based on usage
3. **Multi-Model Classification**: Specific fault type identification
4. **Learning System**: Improve recommendations based on user feedback
