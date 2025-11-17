from pydantic import BaseModel, validator
from typing import Optional, List

# Request Schemas
class FaceRegistrationRequest(BaseModel):
    emp_id: int
    employee_name: str
    face_images: List[str]  # List of base64 encoded images
    
    @validator('emp_id')
    def validate_emp_id(cls, v):
        if v <= 0:
            raise ValueError('Employee ID must be positive')
        return v

    @validator('face_images')
    def validate_face_images(cls, v):
        if len(v) != 4:
            raise ValueError('Exactly 4 face images are required')
        return v

class FaceVerificationRequest(BaseModel):
    emp_id: int
    face_image: str  # Base64 encoded image
    
    @validator('emp_id')
    def validate_emp_id(cls, v):
        if v <= 0:
            raise ValueError('Employee ID must be positive')
        return v

# Response Schemas
class FaceRegistrationResponse(BaseModel):
    success: bool
    message: str
    employee_id: int
    faces_registered: int

class FaceVerificationResponse(BaseModel):
    success: bool
    message: str
    employee_id: int
    confidence_score: float
    match_found: bool