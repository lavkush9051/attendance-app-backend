from pydantic import BaseModel, validator
from typing import Optional

# Request Schemas
class AttendanceReportQuery(BaseModel):
    emp_id: Optional[int] = None
    month: int
    year: int

    @validator('month')
    def validate_month(cls, v):
        if not 1 <= v <= 12:
            raise ValueError('Month must be between 1 and 12')
        return v

    @validator('year')
    def validate_year(cls, v):
        if v < 2000 or v > 2100:
            raise ValueError('Year must be between 2000 and 2100')
        return v