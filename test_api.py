import requests
import json

def test_prediction():
    url = "http://localhost:8000/predict"
    payload = {
        "sensors": {
            "ENGINE_RPM": 3000.0,
            "SPEED": 120.0,
            "ENGINE_COOLANT_TEMP": 105.0,
            "ENGINE_LOAD": 85.0,
            "INTAKE_MANIFOLD_PRESSURE": 50.0
        },
        "mark": "bmw",
        "model_name": "m4_competition"
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=4)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_prediction()
