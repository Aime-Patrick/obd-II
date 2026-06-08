from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional

from services.recommendation_engine import RecommendationEngine
from services import ml_model

router = APIRouter(tags=["Prediction"])

recommendation_engine = RecommendationEngine()


class DiagnosticRequest(BaseModel):
    model_config = {"protected_namespaces": ()}

    sensors: Dict[str, float]
    mark: Optional[str] = None
    model_name: Optional[str] = None
    fuel_type: Optional[str] = None
    automatic: Optional[str] = None
    include_recommendations: bool = True


@router.post("/predict")
def predict(request: DiagnosticRequest):
    try:
        ml_model.ensure_loaded()
        prediction, confidence = ml_model.predict_from_sensors(request.sensors)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

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
        "severity": severity,
        "model_version": ml_model.get_info().get("model_version"),
    }

    if request.include_recommendations:
        response["analysis"] = recommendation_engine.generate_recommendations(
            request.sensors,
            bool(prediction),
            confidence,
        )

    return response
