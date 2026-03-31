from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import joblib
import pandas as pd
import json
import os
from services.recommendation_engine import RecommendationEngine

router = APIRouter(tags=["Prediction"])

# Path to model and metadata
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "obd_model.joblib")
METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "model_metadata.json")

# Load model and metadata
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

class DiagnosticRequest(BaseModel):
    model_config = {'protected_namespaces': ()}

    sensors: Dict[str, float]
    mark: Optional[str] = None
    model_name: Optional[str] = None
    fuel_type: Optional[str] = None
    automatic: Optional[str] = None
    include_recommendations: bool = True

@router.post("/predict")
def predict(request: DiagnosticRequest):
    load_ml_model()
    
    if model is None or metadata is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    # Prepare input
    input_data = metadata.copy()
    
    for key, value in request.sensors.items():
        std_key = key.upper().strip().replace(" ", "_")
        if std_key in input_data:
            input_data[std_key] = value
        elif std_key + "(KPA)" in input_data:
            input_data[std_key + "(KPA)"] = value

    if request.mark:
        mark_key = f"MARK_{request.mark.lower()}"
        if mark_key in input_data:
            for k in input_data:
                if k.startswith("MARK_"): input_data[k] = 0
            input_data[mark_key] = 1

    if request.model_name:
        model_key = f"MODEL_{request.model_name.lower().replace(' ', '_')}"
        if model_key in input_data:
            for k in input_data:
                if k.startswith("MODEL_"): input_data[k] = 0
            input_data[model_key] = 1

    df_input = pd.DataFrame([input_data])
    feature_order = list(metadata.keys())
    df_input = df_input[feature_order]

    try:
        prediction = model.predict(df_input)[0]
        probabilities = model.predict_proba(df_input)[0]
        confidence = float(max(probabilities))
        
        if prediction:
            if confidence > 0.85:
                severity = "CRITICAL"
            elif confidence > 0.65:
                severity = "WARNING"
            else:
                severity = "CAUTION"
        else:
            severity = "HEALTHY"
        
        response = {
            "has_fault": bool(prediction),
            "confidence": confidence,
            "status": "Fault Detected" if prediction else "Healthy",
            "severity": severity
        }
        
        if request.include_recommendations and recommendation_engine:
            analysis = recommendation_engine.generate_recommendations(
                request.sensors,
                bool(prediction),
                confidence
            )
            response["analysis"] = analysis
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")
