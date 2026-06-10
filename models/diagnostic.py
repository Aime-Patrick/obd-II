from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from bson import ObjectId

class DiagnosticCreate(BaseModel):
    model_config = {'protected_namespaces': ()}

    vehicle_id: str
    sensor_data: Dict[str, float]
    mark: Optional[str] = None
    model_name: Optional[str] = None

class DiagnosticResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    user_id: str
    vehicle_id: str
    has_fault: bool
    confidence: float
    status: str
    severity: str
    sensor_data: Dict[str, float]
    analysis: Optional[Dict[str, Any]] = None
    model_version: Optional[str] = None
    timestamp: datetime

class DiagnosticInDB(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id", default=None)
    user_id: ObjectId
    vehicle_id: ObjectId
    has_fault: bool
    confidence: float
    status: str
    severity: str
    sensor_data: Dict[str, float]
    analysis: Optional[Dict[str, Any]] = None
    timestamp: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class TrendPoint(BaseModel):
    timestamp: datetime
    value: float

class SensorStats(BaseModel):
    min: float
    max: float
    average: float

class VehicleTrendsResponse(BaseModel):
    sensors: Dict[str, List[Any]]
    stats: Dict[str, Any]
