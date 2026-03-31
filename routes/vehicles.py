from fastapi import APIRouter, HTTPException, status, Depends
from models.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse
from auth.dependencies import get_current_user
from config.database import get_database
from datetime import datetime
from bson import ObjectId
from typing import List
from pymongo import ReturnDocument

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])

@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    vehicle: VehicleCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    vehicle_dict = {
        "user_id": ObjectId(current_user["sub"]),
        "vin": vehicle.vin or f"UNKNOWN-{str(ObjectId())[:8].upper()}",
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "fuel_type": vehicle.fuel_type,
        "created_at": datetime.utcnow()
    }
    
    result = await db.vehicles.insert_one(vehicle_dict)
    vehicle_dict["_id"] = result.inserted_id
    
    return VehicleResponse(
        id=str(result.inserted_id),
        user_id=str(vehicle_dict["user_id"]),
        vin=vehicle.vin,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        fuel_type=vehicle.fuel_type,
        created_at=vehicle_dict["created_at"]
    )

@router.get("", response_model=List[VehicleResponse])
async def get_vehicles(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    vehicles = await db.vehicles.find({"user_id": ObjectId(current_user["sub"])}).to_list(100)
    return [
        VehicleResponse(
            id=str(v["_id"]),
            user_id=str(v["user_id"]),
            vin=v["vin"],
            make=v["make"],
            model=v["model"],
            year=v["year"],
            fuel_type=v.get("fuel_type"),
            created_at=v["created_at"]
        )
        for v in vehicles
    ]

@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    vehicle = await db.vehicles.find_one({
        "_id": ObjectId(vehicle_id),
        "user_id": ObjectId(current_user["sub"])
    })
    
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    
    return VehicleResponse(
        id=str(vehicle["_id"]),
        user_id=str(vehicle["user_id"]),
        vin=vehicle["vin"],
        make=vehicle["make"],
        model=vehicle["model"],
        year=vehicle["year"],
        fuel_type=vehicle.get("fuel_type"),
        created_at=vehicle["created_at"]
    )

@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: str,
    vehicle_update: VehicleUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    # Build update dict with only provided fields
    update_data = {k: v for k, v in vehicle_update.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    
    result = await db.vehicles.find_one_and_update(
        {"_id": ObjectId(vehicle_id), "user_id": ObjectId(current_user["sub"])},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )
    
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    
    return VehicleResponse(
        id=str(result["_id"]),
        user_id=str(result["user_id"]),
        vin=result["vin"],
        make=result["make"],
        model=result["model"],
        year=result["year"],
        fuel_type=result.get("fuel_type"),
        created_at=result["created_at"]
    )

@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    result = await db.vehicles.delete_one({
        "_id": ObjectId(vehicle_id),
        "user_id": ObjectId(current_user["sub"])
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
