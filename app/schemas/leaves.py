from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional, List
from enum import Enum

class LeaveStatus(str, Enum):
    PENDING = "Pending"
    L1_APPROVED = "L1 Approved"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"

class ApprovalStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class LeaveType(str, Enum):
    CASUAL_LEAVE = "Casual Leave"
    EARNED_LEAVE = "Earned Leave"
    HALF_PAY_LEAVE = "Half Pay Leave"
    MEDICAL_LEAVE = "Medical Leave"
    SPECIAL_LEAVE = "Special Leave"
    CHILD_CARE_LEAVE = "Child Care Leave"
    PARENTAL_LEAVE = "Parental Leave"

# Request Schemas
class LeaveRequestCreate(BaseModel):
    from_date: date
    to_date: date
    leave_type: str
    reason: str

    @validator('to_date')
    def validate_date_range(cls, v, values):
        if 'from_date' in values and v < values['from_date']:
            raise ValueError('End date must be after start date')
        return v

class LeaveActionRequest(BaseModel):
    leave_req_id: int
    action: str
    admin_id: int
    remarks: Optional[str] = None

    @validator('action')
    def validate_action(cls, v):
        if v.lower() not in ['approve', 'reject', 'cancel']:
            raise ValueError('Action must be approve, reject, or cancel')
        return v.lower()

class LeaveBalanceQuery(BaseModel):
    emp_id: int

# Response Schemas
class LeaveTypeResponse(BaseModel):
    type: str
    abrev: str
    total: int

    class Config:
        from_attributes = True

class LeaveBalanceItem(BaseModel):
    type: str
    accrued: float
    held: float
    committed: float
    available: float

class LeaveBalanceResponse(BaseModel):
    emp_id: int
    types: List[LeaveBalanceItem]
    totals: dict

class LeaveRequestBasicResponse(BaseModel):
    id: int
    emp_id: int
    employee_name: str
    emp_department: str
    leave_type_name: str
    start_date: str
    end_date: str
    reason: str
    status: str
    l1_status: str
    l2_status: str
    remarks: str
    applied_date: str

class LeaveActionResponse(BaseModel):
    status: str
    remarks: Optional[str] = None

class AttachmentMeta(BaseModel):
    id: int
    original_name: str
    mime_type: str
    size_bytes: int
    url: str

class AttachmentResponse(BaseModel):
    has_attachment: bool
    items: List[AttachmentMeta]

# Updated Response Schemas for Service Layer
class LeaveRequestResponse(BaseModel):
    request_id: int
    employee_id: int
    employee_name: str
    from_date: date
    to_date: date
    leave_type: str
    reason: str
    total_days: float
    status: str  # HOLD/RELEASE/COMMIT
    l1_status: str
    l2_status: str
    created_at: int  # Using ID as placeholder
    remarks: Optional[str] = None
    
    class Config:
        from_attributes = True

class LeaveRequestDetailResponse(BaseModel):
    request_id: int
    employee_id: int
    employee_name: str
    employee_department: Optional[str]
    employee_designation: Optional[str]
    from_date: date
    to_date: date
    leave_type: str
    reason: str
    total_days: float
    status: str
    l1_status: str
    l2_status: str
    can_approve: bool
    action_level: Optional[str]  # "L1" or "L2"
    created_at: int
    remarks : Optional[str]
    
    class Config:
        from_attributes = True

class LeaveStatusUpdate(BaseModel):
    action: str  # "approve" or "reject"
    comments: Optional[str] = None
    
    @validator('action')
    def validate_action(cls, v):
        if v.lower() not in ['approve', 'reject']:
            raise ValueError('Action must be approve or reject')
        return v.lower()

class LeaveBalanceResponse(BaseModel):
    leave_type: str
    allocated_days: float
    used_days: float
    carried_forward: float
    available_days: float
    year: int
    
    class Config:
        from_attributes = True