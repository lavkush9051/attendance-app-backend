from pydantic import BaseModel, validator
from datetime import date, time, datetime
from typing import Optional, List
from enum import Enum

class AttendanceStatus(str, Enum):
    PENDING = "Pending"
    L1_APPROVED = "L1 Approved"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class ApprovalStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

# Request Schemas
class AttendanceRegularizationCreate(BaseModel):
    request_date: date
    clock_in_time: time
    clock_out_time: time
    reason: str
    shift: str

    @validator('clock_out_time')
    def validate_time_range(cls, v, values):
        if 'clock_in_time' in values and v <= values['clock_in_time']:
            raise ValueError('Clock out time must be after clock in time')
        return v

class AttendanceActionRequest(BaseModel):
    attendance_request_id: int
    action: str
    admin_id: int

    @validator('action')
    def validate_action(cls, v):
        if v.lower() not in ['approve', 'reject']:
            raise ValueError('Action must be approve or reject')
        return v.lower()

class AttendanceQuery(BaseModel):
    emp_id: int
    start: date
    end: date

class RegularizationQuery(BaseModel):
    emp_id: int
    admin: bool = False

# Response Schemas
class AttendanceDay(BaseModel):
    date: str
    clockIn: str
    clockOut: str
    shift: str

class AttendanceResponse(BaseModel):
    attendance: List[AttendanceDay]
    holidays: List[str]
    absent: int
    average_working: str
    average_late: str
    shift: str

class RegularizationRequestResponse(BaseModel):
    id: int
    emp_id: int
    employee_name: str
    emp_department: str
    date: str
    clock_in: str
    clock_out: str
    reason: str
    status: str
    l1_status: str
    l2_status: str
    shift: str
    applied_date: str

class AttendanceActionResponse(BaseModel):
    status: str

class AttendanceRequestResponse(BaseModel):
    request_id: int
    employee_id: int
    employee_name: str
    request_date: date
    clock_in: time
    clock_out: time
    reason: str
    status: str
    l1_status: str
    l2_status: str
    shift: str
    applied_date: Optional[datetime] = None
    created_at: int  # Using ID as placeholder timestamp
    
    class Config:
        from_attributes = True

class AttendanceRequestDetailResponse(BaseModel):
    request_id: int
    employee_id: int
    employee_name: str
    employee_department: Optional[str]
    employee_designation: Optional[str]
    request_date: date
    clock_in: time
    clock_out: time
    reason: str
    status: str
    l1_status: str
    l2_status: str
    shift: str
    can_approve: bool
    action_level: Optional[str]  # "L1" or "L2"
    applied_date: Optional[datetime] = None
    created_at: int
    
    class Config:
        from_attributes = True

class AttendanceStatusUpdate(BaseModel):
    status: str  # "approve" or "reject" - frontend uses "status", not "action" 
    manager_id: int
    
    @validator('status')
    def validate_action(cls, v):
        if v.lower() not in ['approve', 'reject']:
            raise ValueError('Status must be approve or reject')
        return v.lower()