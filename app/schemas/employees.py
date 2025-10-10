from pydantic import BaseModel
from typing import Optional, List

# Request Schemas
class WeekoffUpdateRequest(BaseModel):
    emp_ids: List[int]
    weekoff: str

class ReportingLevelsQuery(BaseModel):
    emp_id: int
    l1_id: int
    l2_id: int

# Response Schemas
class EmployeeResponse(BaseModel):
    emp_id: int
    emp_name: str
    emp_department: Optional[str] = None
    emp_designation: Optional[str] = None
    emp_email: Optional[str] = None
    emp_contact: Optional[str] = None
    emp_l1: Optional[int] = None
    emp_l2: Optional[int] = None
    emp_shift: Optional[str] = None
    emp_weekoff: Optional[str] = None

    class Config:
        from_attributes = True

class ReportingLevelPerson(BaseModel):
    name: str
    designation: str
    email: str
    mobile: str
    department: str
    avatarColor: str

class ReportingLevelsResponse(BaseModel):
    employee: ReportingLevelPerson
    l1: ReportingLevelPerson
    l2: ReportingLevelPerson

class WeekoffUpdateResponse(BaseModel):
    status: str
    updated: int