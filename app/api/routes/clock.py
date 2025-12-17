from fastapi import APIRouter, File, UploadFile, Form, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from typing import Dict, Any
from app.face_engine import FaceEngine
from app.services.geo_fence_service import is_within_geofence, calculate_distance_meters
from app.dependencies import get_current_user_emp_id, get_clock_service, get_face_service, get_geofence_service
from app.auth import get_current_user
from app.services.clock_service import ClockService
from app.services.face_service import FaceService
from app.services.geofence_service import GeofenceService
import numpy as np

router = APIRouter()

IST = ZoneInfo("Asia/Kolkata")
CLOCKIN_THRESHOLD = 0.75
OFFICE_LATITUDE = 19.1158577
OFFICE_LONGITUDE = 72.8934000
GEOFENCE_RADIUS_METERS = 50

engine = FaceEngine()

@router.post("/clockin")
async def clockin(
    file: UploadFile = File(...),
    face_user_emp_id: str = Form(...),
    shift: str = Form(...),
    lat: float = Form(0.0),
    lon: float = Form(0.0),
    current_emp_id: int = Depends(get_current_user_emp_id),
    clock_service: ClockService = Depends(get_clock_service),
    face_service: FaceService = Depends(get_face_service),
    geofence_service: GeofenceService = Depends(get_geofence_service)
):
    """Clock-in endpoint with face recognition and geofencing validation"""
    
    print(f"[LOG] /clockin called by user {current_emp_id} for emp_id {face_user_emp_id}, shift={shift}, location=({lat},{lon})")
    
    # Validate that user can only clock in for themselves
    if int(face_user_emp_id) != current_emp_id:
        print(f"[ERROR] /clockin authorization failed: user {current_emp_id} trying to clock in for {face_user_emp_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only clock in for yourself"
        )
    
    print(f"[LOG] Clock-in attempt by emp_id {face_user_emp_id} for shift {shift} at location ({lat}, {lon})")
    
    # --- 1. Geofencing Validation using database-driven geofence service ---
    validation_result = geofence_service.validate_employee_location(
        emp_id=int(face_user_emp_id),
        user_lat=lat,
        user_lon=lon
    )
    
    if not validation_result["is_valid"]:
        print(f"[GEO_LOG] Geofence validation failed for emp {face_user_emp_id}: {validation_result['message']}")
        return {
            "status": "failed",
            "reason": validation_result["message"],
            "code": validation_result.get("code"),
            "distance": validation_result.get("distance"),
            "nearest_block": validation_result.get("nearest_block"),
            "allowed_radius": validation_result.get("allowed_radius")
        }
    
    print(f"[GEO_LOG] ✅ Geofence validation passed for emp {face_user_emp_id}: {validation_result['message']}")
    
    # --- 2. Face Recognition ---
    content = await file.read()
    live_descriptor = engine.extract_descriptor(content)
    if live_descriptor is None:
        return {"status": "failed", "reason": "No face detected"}

    now_ist = datetime.now(IST)
    today_ist = now_ist.date()
    time_ist = now_ist.time().replace(microsecond=0)

    try:
        # Check if employee has face records using service
        face_status = face_service.get_employee_face_status(int(face_user_emp_id))
        print(f"[DEBUG] Face status for emp_id {face_user_emp_id}: {face_status}")
        
        if not face_status.get("has_faces_registered", False):
            print(f"[ERROR] No faces registered for employee {face_user_emp_id}")
            return {"status": "failed", "reason": "User not found"}

        # Get face records for comparison (since service doesn't have direct getter, we need repository access)
        # This is a limitation - need to access repository for face data comparison
        from app.repositories.face_repo import FaceRepository
        from app.database import get_db
        from sqlalchemy.orm import Session
        
        # Get database session for face repository
        db_gen = get_db()
        db_session = next(db_gen)
        temp_face_repo = FaceRepository(db_session)
        users = temp_face_repo.get_by_emp_id(int(face_user_emp_id))
        
        if not users:
            return {"status": "failed", "reason": "User not found"}
            
        # Validate shift exists (this logic is embedded in service but we need it here for validation)
        # Since ClockService doesn't expose shift validation separately, we keep this validation
        
    except Exception as e:
        return {"status": "failed", "reason": f"Database error: {str(e)}"}

    # Compare faces
    for user in users:
        db_desc = np.array(user.embedding)
        distance = np.linalg.norm(live_descriptor - db_desc)
        print(f"[LOG] Compared with {user.name} → Distance: {distance:.4f}")

        if distance < CLOCKIN_THRESHOLD:
            # --- CLOCK IN LOGIC START ---
            try:
                print(f"[DEBUG] Starting clock-in process for {user.name}")
                
                # Use already read content for base64 encoding (avoid reading file again)
                import base64
                face_image_b64 = base64.b64encode(content).decode('utf-8')
                
                # Create service request
                from app.schemas.clock import ClockInRequest
                clock_request = ClockInRequest(
                    emp_id=int(face_user_emp_id),
                    face_image=face_image_b64,
                    clockin_time=time_ist,
                    latitude=lat,
                    longitude=lon,
                    shift=shift
                )
                
                print(f"[DEBUG] Clock request created: emp_id={clock_request.emp_id}, shift={clock_request.shift}")
                
                # Use service to process clock-in
                clock_response = clock_service.process_clock_in(clock_request)
                
                print(f"[DEBUG] Clock service response: success={clock_response.success}, message={clock_response.message}")
                
                if clock_response.success:
                    result = {
                        "status": "success",
                        "user": user.name,
                        "distance": round(distance, 4),
                        "clockin_time": str(clock_response.clockin_time),
                        "shift": clock_response.shift,
                        "message": clock_response.message
                    }
                    print(f"[LOG] /clockin success: {result}")
                    return result
                else:
                    print(f"[ERROR] /clockin failed: {clock_response.message}")
                    return {"status": "failed", "reason": clock_response.message}
                    
            except Exception as e:
                print(f"[ERROR] /clockin exception: {str(e)}")
                import traceback
                traceback.print_exc()
                return {"status": "failed", "reason": f"Clock-in failed: {str(e)}"}

    result = {
        "status": "failed",
        "reason": "Face does not match logged-in user"
    }
    print(f"[ERROR] /clockin face recognition failed: {result}")
    return result

@router.put("/clockout")
async def clockout(
    request: Request,
    current_emp_id: int = Depends(get_current_user_emp_id),
    clock_service: ClockService = Depends(get_clock_service)
):
    """Clock-out endpoint"""
    data = await request.json()
    print(f"[LOG] /clockout called by user {current_emp_id}, raw body: {data}")
    emp_id = data.get("emp_id")
    
    # Validate that user can only clock out for themselves
    if int(emp_id) != current_emp_id:
        print(f"[ERROR] /clockout authorization failed: user {current_emp_id} trying to clock out for {emp_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only clock out for yourself"
        )
    
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()
    time_ist = now_ist.time().replace(microsecond=0)
    
    try:
        # Create service request for clock-out
        from app.schemas.clock import ClockOutRequest
        clockout_request = ClockOutRequest(
            emp_id=emp_id,
            clockout_time=time_ist
        )
        
        # Use service to process clock-out
        clockout_response = clock_service.process_clock_out(clockout_request)
        
        if clockout_response.success:
            result = {"status": "success", "clockout_time": str(time_ist)}
            print(f"[LOG] /clockout success: {result}")
            return result
        else:
            print(f"[ERROR] /clockout failed: {clockout_response.message}")
            return {"status": "failed", "error": clockout_response.message}
            
    except Exception as e:
        print(f"[ERROR] /clockout exception: {str(e)}")
        return {"status": "failed", "error": str(e)}

def within_clockin_window(now_ist: datetime, shift_start_time, minutes: int = 15) -> bool:
    """
    True if now_ist is within [shift_start - minutes, shift_start + minutes].
    Handles windows that cross midnight (e.g., 00:05 start).
    """
    # anchor shift start to *today* in IST
    start_today = datetime.combine(now_ist.date(), shift_start_time).replace(tzinfo=IST)
    window = timedelta(minutes=minutes)
    ws_today = start_today - window
    we_today = start_today + window

    # also consider the window for *tomorrow* (covers early clock-in before midnight for a 00:xx shift)
    start_tom = start_today + timedelta(days=1)
    ws_tom = start_tom - window
    we_tom = start_tom + window

    return (ws_today <= now_ist <= we_today) or (ws_tom <= now_ist <= we_tom)
