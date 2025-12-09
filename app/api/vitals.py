from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.models.user import User
from app.models.vital import Vital, VitalType
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class VitalCreate(BaseModel):
    type: VitalType
    value: float
    unit: str
    timestamp: Optional[datetime] = None

@router.post("/", response_model=Vital, summary="Record a new vital sign", status_code=201)
async def create_vital(
    vital_in: VitalCreate,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Record a new vital sign measurement for the authenticated user.
    
    **Requires authentication:** Yes (Bearer token)
    
    **Vital Types:**
    - `ecg`: Electrocardiogram data
    - `bpm`: Beats per minute
    - `gyroscope`: Gyroscope sensor data
    - `heart_rate`: Heart rate measurement
    
    **Parameters:**
    - **type**: Type of vital sign
    - **value**: Numeric measurement value
    - **unit**: Unit of measurement (e.g., "bpm", "degrees", etc.)
    - **timestamp**: Optional timestamp (defaults to current time)
    
    **Returns:**
    - Created vital sign record
    """
    vital = Vital(
        type=vital_in.type,
        value=vital_in.value,
        unit=vital_in.unit,
        user=current_user,
        timestamp=vital_in.timestamp or datetime.utcnow()
    )
    await vital.insert()
    return vital

@router.get("/", response_model=List[Vital], summary="Get vital signs history")
async def read_vitals(
    type: Optional[VitalType] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Get vital signs history for the authenticated user.
    
    **Requires authentication:** Yes (Bearer token)
    
    **Query Parameters:**
    - **type**: Optional filter by vital type (ecg, bpm, gyroscope, heart_rate)
    - **limit**: Maximum number of results (default: 100)
    - **skip**: Number of results to skip for pagination (default: 0)
    
    **Returns:**
    - List of vital signs (most recent first)
    """
    query = Vital.find(Vital.user.id == current_user.id)
    if type:
        query = query.find(Vital.type == type)
    
    return await query.sort(-Vital.timestamp).skip(skip).limit(limit).to_list()
