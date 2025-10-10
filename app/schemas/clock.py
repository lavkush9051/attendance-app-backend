from pydantic import BaseModel, validator
from datetime import time, date
from typing import Optional

# Request Schemas
class ClockInRequest(BaseModel):
    emp_id: int
    face_image: Optional[str] = None  # Base64 encoded image
    clockin_time: Optional[time] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    shift: str = "General"

    @validator('latitude')
    def validate_latitude(cls, v):
        if v is not None and not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v

    @validator('longitude')
    def validate_longitude(cls, v):
        if v is not None and not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v

class ClockOutRequest(BaseModel):
    emp_id: int
    clockout_time: Optional[time] = None

# Response Schemas
class ClockInResponse(BaseModel):
    success: bool
    message: str
    clockin_id: Optional[int] = None
    clockin_time: Optional[time] = None
    employee_id: int
    shift: str

class ClockOutResponse(BaseModel):
    success: bool
    message: str
    clockin_id: Optional[int] = None
    clockin_time: Optional[time] = None
    clockout_time: Optional[time] = None
    worked_hours: float
    employee_id: int

class AttendanceRecordResponse(BaseModel):
    clockin_id: int
    employee_id: int
    date: date
    clockin_time: Optional[time]
    clockout_time: Optional[time]
    worked_hours: float
    shift: str
    status: str  # "Complete", "Incomplete"
    
    class Config:
        from_attributes = True