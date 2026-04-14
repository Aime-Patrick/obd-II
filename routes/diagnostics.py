from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel
from models.diagnostic import DiagnosticCreate, DiagnosticResponse, VehicleTrendsResponse
from auth.dependencies import get_current_user
from config.database import get_database
from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Any
import joblib
import pandas as pd
import json
import os
from services.recommendation_engine import RecommendationEngine
from services.email_service import email_service
from services.sensor_analyzer import SensorAnalyzer

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])

# Load ML model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "obd_model.joblib")
METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "model_metadata.json")

model = None
metadata = None
recommendation_engine = None

def load_ml_model():
    global model, metadata, recommendation_engine
    if model is None:
        model = joblib.load(MODEL_PATH)
        with open(METADATA_PATH, "r") as f:
            metadata = json.load(f)
        recommendation_engine = RecommendationEngine()

@router.post("", response_model=DiagnosticResponse, status_code=status.HTTP_201_CREATED)
async def create_diagnostic(
    diagnostic: DiagnosticCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    try:
        load_ml_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML model failed to load: {e}")

    # Verify vehicle belongs to user
    vehicle = await db.vehicles.find_one({
        "_id": ObjectId(diagnostic.vehicle_id),
        "user_id": ObjectId(current_user["sub"])
    })
    
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    # Reject requests where all sensor values are zero — no real OBD data
    non_zero = [v for v in diagnostic.sensor_data.values() if v != 0.0]
    if not non_zero:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No valid sensor data. Connect your OBD-II device and try again."
        )

    # ── Step 1: Rule-based sensor analysis (primary signal) ──────────────────
    sensor_analyzer_instance = SensorAnalyzer()
    abnormal_sensors = sensor_analyzer_instance.analyze_sensors(diagnostic.sensor_data)
    
    critical_count = sum(1 for s in abnormal_sensors if s["status"] == "critical")
    warning_count  = sum(1 for s in abnormal_sensors if s["status"] == "warning")
    
    # ── Step 2: ML model ─────────────────────────────────────────────────────
    # Build input using all available sensor readings.
    # Fall back to training medians for any sensor the device didn't send.
    feature_order = metadata.get("__feature_order__", list(metadata.keys()))
    feature_order = [f for f in feature_order if f != "__feature_order__"]

    input_data = {}
    for feat in feature_order:
        # Check if the app sent this sensor (case-insensitive)
        matched = next(
            (v for k, v in diagnostic.sensor_data.items()
             if k.upper().strip().replace(" ", "_") == feat),
            None
        )
        input_data[feat] = matched if matched is not None else metadata.get(feat, 0.0)

    # Compute derived features
    rpm   = input_data.get("ENGINE_RPM", 1)
    load  = input_data.get("ENGINE_LOAD", 1)
    temp  = input_data.get("ENGINE_COOLANT_TEMP", 0)
    thr   = input_data.get("THROTTLE_POS", 0)
    ait   = input_data.get("AIR_INTAKE_TEMP", temp)
    stft1 = input_data.get("SHORT_TERM_FUEL_TRIM_BANK_1", 0)
    ltft2 = input_data.get("LONG_TERM_FUEL_TRIM_BANK_2", 0)

    if "RPM_LOAD_RATIO" in feature_order:
        input_data["RPM_LOAD_RATIO"] = rpm / max(load, 1)
    if "TEMP_RPM_RATIO" in feature_order:
        input_data["TEMP_RPM_RATIO"] = temp / max(rpm, 1)
    if "THROTTLE_LOAD_DIFF" in feature_order:
        input_data["THROTTLE_LOAD_DIFF"] = thr - load
    if "FUEL_TRIM_TOTAL" in feature_order:
        input_data["FUEL_TRIM_TOTAL"] = stft1 + ltft2
    if "INTAKE_TEMP_DIFF" in feature_order:
        input_data["INTAKE_TEMP_DIFF"] = temp - ait

    df_input = pd.DataFrame([input_data])[feature_order]
    try:
        ml_prediction = bool(model.predict(df_input)[0])
        ml_confidence = float(max(model.predict_proba(df_input)[0]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML prediction failed: {e}")

    # ── Step 3: Combine signals ───────────────────────────────────────────────
    if critical_count > 0:
        prediction = True
        confidence = max(ml_confidence, 0.92)
        severity = "CRITICAL"
    elif warning_count > 0:
        prediction = True
        confidence = max(ml_confidence, 0.78)
        severity = "WARNING"
    elif ml_prediction and ml_confidence > 0.70:
        prediction = True
        confidence = ml_confidence
        severity = "CAUTION"
    else:
        prediction = False
        confidence = 1.0 - ml_confidence if not ml_prediction else 0.65
        severity = "HEALTHY"
    
    # Generate recommendations
    analysis = recommendation_engine.generate_recommendations(
        diagnostic.sensor_data,
        bool(prediction),
        confidence
    )
    
    # Save to database
    diagnostic_dict = {
        "user_id": ObjectId(current_user["sub"]),
        "vehicle_id": ObjectId(diagnostic.vehicle_id),
        "has_fault": bool(prediction),
        "confidence": confidence,
        "status": "Fault Detected" if prediction else "Healthy",
        "severity": severity,
        "sensor_data": diagnostic.sensor_data,
        "analysis": analysis,
        "timestamp": datetime.utcnow()
    }
    
    result = await db.diagnostics.insert_one(diagnostic_dict)
    diagnostic_dict["_id"] = result.inserted_id
    
    # Send Email Report in background
    user = await db.users.find_one({"_id": ObjectId(current_user["sub"])})
    if user and user.get("email"):
        # Send diagnostic report
        background_tasks.add_task(
            email_service.send_diagnostic_report,
            user["email"],
            {
                "make": vehicle.get("make"),
                "model": vehicle.get("model"),
                "year": vehicle.get("year")
            },
            analysis
        )
        
        # Send maintenance alert if critical/warning
        if severity in ["CRITICAL", "WARNING"]:
            background_tasks.add_task(
                email_service.send_maintenance_alert,
                user["email"],
                {
                    "make": vehicle.get("make"),
                    "model": vehicle.get("model")
                },
                f"{severity} Fault Detected",
                f"The AI has identified a {severity.lower()} issue that requires attention. Please check your vehicle."
            )
    
    return DiagnosticResponse(
        id=str(result.inserted_id),
        user_id=str(diagnostic_dict["user_id"]),
        vehicle_id=str(diagnostic_dict["vehicle_id"]),
        has_fault=diagnostic_dict["has_fault"],
        confidence=diagnostic_dict["confidence"],
        status=diagnostic_dict["status"],
        severity=diagnostic_dict["severity"],
        sensor_data=diagnostic_dict["sensor_data"],
        analysis=diagnostic_dict["analysis"],
        timestamp=diagnostic_dict["timestamp"]
    )

@router.get("", response_model=List[DiagnosticResponse])
async def get_diagnostics(
    vehicle_id: str = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    query = {"user_id": ObjectId(current_user["sub"])}
    if vehicle_id:
        query["vehicle_id"] = ObjectId(vehicle_id)
    
    diagnostics = await db.diagnostics.find(query).sort("timestamp", -1).limit(50).to_list(50)
    
    return [
        DiagnosticResponse(
            id=str(d["_id"]),
            user_id=str(d["user_id"]),
            vehicle_id=str(d["vehicle_id"]),
            has_fault=d["has_fault"],
            confidence=d["confidence"],
            status=d["status"],
            severity=d["severity"],
            sensor_data=d["sensor_data"],
            analysis=d.get("analysis"),
            timestamp=d["timestamp"]
        )
        for d in diagnostics
    ]

@router.get("/trends/{vehicle_id}")
async def get_diagnostic_trends(
    vehicle_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    # Verify vehicle belongs to user
    vehicle = await db.vehicles.find_one({
        "_id": ObjectId(vehicle_id),
        "user_id": ObjectId(current_user["sub"])
    })
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    # Query last 30 diagnostics ordered by timestamp ascending
    diagnostics = await db.diagnostics.find(
        {"vehicle_id": ObjectId(vehicle_id), "user_id": ObjectId(current_user["sub"])}
    ).sort("timestamp", 1).limit(30).to_list(30)

    # Collect {timestamp, value} per sensor
    sensor_points: Dict[str, List[Dict]] = {}
    for diag in diagnostics:
        ts = diag["timestamp"].isoformat()
        for sensor_name, value in diag.get("sensor_data", {}).items():
            if sensor_name not in sensor_points:
                sensor_points[sensor_name] = []
            sensor_points[sensor_name].append({"timestamp": ts, "value": value})

    # Filter sensors with fewer than 2 data points
    sensor_points = {k: v for k, v in sensor_points.items() if len(v) >= 2}

    # Compute stats per sensor
    stats: Dict[str, Dict] = {}
    for sensor_name, points in sensor_points.items():
        values = [p["value"] for p in points]
        stats[sensor_name] = {
            "min": min(values),
            "max": max(values),
            "average": sum(values) / len(values)
        }

    return {"sensors": sensor_points, "stats": stats}


@router.get("/{diagnostic_id}", response_model=DiagnosticResponse)
async def get_diagnostic(
    diagnostic_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    diagnostic = await db.diagnostics.find_one({
        "_id": ObjectId(diagnostic_id),
        "user_id": ObjectId(current_user["sub"])
    })
    
    if not diagnostic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic not found")
    
    return DiagnosticResponse(
        id=str(diagnostic["_id"]),
        user_id=str(diagnostic["user_id"]),
        vehicle_id=str(diagnostic["vehicle_id"]),
        has_fault=diagnostic["has_fault"],
        confidence=diagnostic["confidence"],
        status=diagnostic["status"],
        severity=diagnostic["severity"],
        sensor_data=diagnostic["sensor_data"],
        analysis=diagnostic.get("analysis"),
        timestamp=diagnostic["timestamp"]
    )


# ── Data collection for model retraining ─────────────────────────────────────

class DiagnosticLabel(BaseModel):
    confirmed_fault: bool  # True = user confirms fault, False = user confirms healthy

@router.patch("/{diagnostic_id}/label", status_code=status.HTTP_200_OK)
async def label_diagnostic(
    diagnostic_id: str,
    body: DiagnosticLabel,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """User labels a past diagnostic as truly faulty or healthy.
    This data is used to retrain the model with real-world examples."""
    result = await db.diagnostics.update_one(
        {"_id": ObjectId(diagnostic_id), "user_id": ObjectId(current_user["sub"])},
        {"$set": {"user_label": body.confirmed_fault, "labeled_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    return {"message": "Label saved. Thank you for improving the model."}
