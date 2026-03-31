import requests
import json

# Test endpoint
url = "http://127.0.0.1:8001/predict"

# Test Case 1: Normal readings
print("=" * 60)
print("TEST 1: Normal Vehicle Readings")
print("=" * 60)

normal_data = {
    "sensors": {
        "ENGINE_COOLANT_TEMP": 88,
        "ENGINE_LOAD": 45,
        "ENGINE_RPM": 1800,
        "FUEL_PRESSURE": 50,
        "MAF": 8,
        "THROTTLE_POS": 25,
        "SPEED": 60,
        "AIR_INTAKE_TEMP": 35
    },
    "mark": "toyota",
    "model_name": "corolla",
    "include_recommendations": True
}

response = requests.post(url, json=normal_data)
print(json.dumps(response.json(), indent=2))

# Test Case 2: Engine overheating
print("\n" + "=" * 60)
print("TEST 2: Engine Overheating Scenario")
print("=" * 60)

overheating_data = {
    "sensors": {
        "ENGINE_COOLANT_TEMP": 110,  # Critical!
        "ENGINE_LOAD": 85,  # High
        "ENGINE_RPM": 2200,
        "FUEL_PRESSURE": 48,
        "MAF": 12,
        "THROTTLE_POS": 65,
        "SPEED": 80,
        "AIR_INTAKE_TEMP": 55
    },
    "mark": "honda",
    "model_name": "fit",
    "include_recommendations": True
}

response = requests.post(url, json=overheating_data)
print(json.dumps(response.json(), indent=2))

# Test Case 3: Multiple issues
print("\n" + "=" * 60)
print("TEST 3: Multiple Sensor Issues")
print("=" * 60)

multiple_issues_data = {
    "sensors": {
        "ENGINE_COOLANT_TEMP": 98,  # Warning
        "ENGINE_LOAD": 92,  # Critical
        "ENGINE_RPM": 4200,  # Warning
        "FUEL_PRESSURE": 28,  # Critical
        "MAF": 18,  # Warning
        "THROTTLE_POS": 88,  # Warning
        "SPEED": 130,  # Warning
        "AIR_INTAKE_TEMP": 65
    },
    "mark": "volkswagen",
    "model_name": "polo",
    "include_recommendations": True
}

response = requests.post(url, json=multiple_issues_data)
print(json.dumps(response.json(), indent=2))

# Test Case 4: Without recommendations
print("\n" + "=" * 60)
print("TEST 4: Prediction Only (No Recommendations)")
print("=" * 60)

simple_data = {
    "sensors": {
        "ENGINE_COOLANT_TEMP": 90,
        "ENGINE_RPM": 2000
    },
    "include_recommendations": False
}

response = requests.post(url, json=simple_data)
print(json.dumps(response.json(), indent=2))
