from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

class VehicleCreate(BaseModel):
    vin: Optional[str] = None
    make: str
    model: str
    year: int
    fuel_type: Optional[str] = None

class VehicleUpdate(BaseModel):
    vin: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    fuel_type: Optional[str] = None

class VehicleResponse(BaseModel):
    id: str
    user_id: str
    vin: Optional[str] = None
    make: str
    model: str
    year: int
    fuel_type: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {ObjectId: str}

class VehicleInDB(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id", default=None)
    user_id: ObjectId
    vin: str
    make: str
    model: str
    year: int
    fuel_type: Optional[str] = None
    created_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
