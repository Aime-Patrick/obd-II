import requests
import json

BASE_URL = "http://127.0.0.1:8001"

# Test 1: Register User
print("=" * 60)
print("TEST 1: Register User")
print("=" * 60)

register_data = {
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
}

response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# Test 2: Login
print("\n" + "=" * 60)
print("TEST 2: Login")
print("=" * 60)

login_data = {
    "email": "test@example.com",
    "password": "password123"
}

response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
print(f"Status: {response.status_code}")
login_response = response.json()
print(json.dumps(login_response, indent=2))

# Get token
token = login_response["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test 3: Create Vehicle
print("\n" + "=" * 60)
print("TEST 3: Create Vehicle")
print("=" * 60)

vehicle_data = {
    "vin": "1HGBH41JXMN109186",
    "make": "Toyota",
    "model": "Corolla",
    "year": 2020,
    "fuel_type": "Gasoline"
}

response = requests.post(f"{BASE_URL}/vehicles", json=vehicle_data, headers=headers)
print(f"Status: {response.status_code}")
vehicle_response = response.json()
print(json.dumps(vehicle_response, indent=2))

vehicle_id = vehicle_response["id"]

# Test 4: Get Vehicles
print("\n" + "=" * 60)
print("TEST 4: Get All Vehicles")
print("=" * 60)

response = requests.get(f"{BASE_URL}/vehicles", headers=headers)
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# Test 5: Run Diagnostic
print("\n" + "=" * 60)
print("TEST 5: Run Diagnostic (Normal)")
print("=" * 60)

diagnostic_data = {
    "vehicle_id": vehicle_id,
    "sensor_data": {
        "ENGINE_COOLANT_TEMP": 88,
        "ENGINE_LOAD": 45,
        "ENGINE_RPM": 1800,
        "FUEL_PRESSURE": 50,
        "MAF": 8,
        "THROTTLE_POS": 25,
        "SPEED": 60
    },
    "mark": "toyota",
    "model_name": "corolla"
}

response = requests.post(f"{BASE_URL}/diagnostics", json=diagnostic_data, headers=headers)
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# Test 6: Run Diagnostic (Critical)
print("\n" + "=" * 60)
print("TEST 6: Run Diagnostic (Critical - Overheating)")
print("=" * 60)

diagnostic_data_critical = {
    "vehicle_id": vehicle_id,
    "sensor_data": {
        "ENGINE_COOLANT_TEMP": 110,
        "ENGINE_LOAD": 92,
        "ENGINE_RPM": 2200,
        "FUEL_PRESSURE": 28,
        "MAF": 18,
        "THROTTLE_POS": 88
    },
    "mark": "toyota",
    "model_name": "corolla"
}

response = requests.post(f"{BASE_URL}/diagnostics", json=diagnostic_data_critical, headers=headers)
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# Test 7: Get Diagnostic History
print("\n" + "=" * 60)
print("TEST 7: Get Diagnostic History")
print("=" * 60)

response = requests.get(f"{BASE_URL}/diagnostics?vehicle_id={vehicle_id}", headers=headers)
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# Test 8: Unauthorized Access
print("\n" + "=" * 60)
print("TEST 8: Unauthorized Access (No Token)")
print("=" * 60)

response = requests.get(f"{BASE_URL}/vehicles")
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED")
print("=" * 60)
