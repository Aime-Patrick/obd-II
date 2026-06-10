"""Deprecated legacy endpoint — use POST /diagnostics instead."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["Prediction (deprecated)"])


@router.post("/predict")
def predict_deprecated():
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "POST /predict is removed. Use POST /diagnostics with a Bearer JWT "
            "and vehicle_id for authenticated diagnostics and recommendations."
        ),
    )
