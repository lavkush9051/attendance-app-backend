from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from app.face_engine import FaceEngine
from app.dependencies import get_current_user_emp_id, get_face_service
from app.auth import get_current_user
from app.services.face_service import FaceService

router = APIRouter()

engine = FaceEngine()

@router.post("/register")
async def register_faces(
    emp_id: int = Form(...),
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    current_emp_id: int = Depends(get_current_user_emp_id),
    face_service: FaceService = Depends(get_face_service)
):
    """Register faces for an employee using face recognition"""
    print(f"[LOG] /register called by user {current_emp_id} for emp_id {emp_id}, name={name}, {len(files) if files else 0} files")
    
    # Users can only register faces for themselves
    if emp_id != current_emp_id:
        print(f"[ERROR] /register authorization failed: user {current_emp_id} trying to register for {emp_id}")
        raise HTTPException(
            status_code=403,
            detail="You can only register faces for yourself"
        )
    
    try:
        # 1) must be exactly 4 files
        if not files or len(files) != 4:
            return JSONResponse(
                status_code=400,
                content={"status": "failed", "reason": "Exactly 4 images are required."}
            )
        
        # Convert uploaded files to base64 for service
        import base64
        face_images = []
        for file in files:
            content = await file.read()
            face_image_b64 = base64.b64encode(content).decode('utf-8')
            face_images.append(face_image_b64)
        
        # Create service request
        from app.schemas.faces import FaceRegistrationRequest
        registration_request = FaceRegistrationRequest(
            emp_id=emp_id,
            employee_name=name,
            face_images=face_images
        )
        
        # Use service to register faces
        response = face_service.register_employee_faces(registration_request)
        
        if response.success:
            result = {"status": "success", "message": response.message}
            print(f"[LOG] /register successful: {result}")
            return JSONResponse(content=result)
        else:
            error_result = {"status": "failed", "reason": response.message}
            print(f"[ERROR] /register failed: {error_result}")
            return JSONResponse(
                status_code=400,
                content=error_result
            )
            
    except Exception as e:
        error_result = {"status": "failed", "error": str(e)}
        print(f"[ERROR] /register exception: {error_result}")
        return JSONResponse(status_code=500, content=error_result)
