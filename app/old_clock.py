from fastapi import APIRouter, File, UploadFile, Form, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from typing import Dict, Any
from app.database import SessionLocal
from app.models import ClockInClockOut, EmpShift, FaceUser, Employee
from app.face_engine import FaceEngine
from app.services.geo_fence_service import is_within_geofence
from app.dependencies import get_current_user_emp_id
from app.auth import get_current_user
import numpy as np

router = APIRouter()

IST = ZoneInfo("Asia/Kolkata")
CLOCKIN_THRESHOLD = 0.75
OFFICE_LATITUDE = 19.1158577
OFFICE_LONGITUDE = 72.8934000
GEOFENCE_RADIUS_METERS = 100

engine = FaceEngine()

@router.post("/clockin")
async def clockin(
    file: UploadFile = File(...),
    face_user_emp_id: str = Form(...),
    shift: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    current_emp_id: int = Depends(get_current_user_emp_id)
):
    """Clock-in endpoint with face recognition and geofencing validation"""
    
    # Validate that user can only clock in for themselves
    if int(face_user_emp_id) != current_emp_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only clock in for yourself"
        )
    
    print(f"[LOG] Clock-in attempt by emp_id {face_user_emp_id} for shift {shift} at location ({lat}, {lon})")
    
    # --- 1. Geofencing Validation ---
    is_location_valid = is_within_geofence(
        user_lat=lat,
        user_lon=lon,
        office_lat=OFFICE_LATITUDE,
        office_lon=OFFICE_LONGITUDE,
        radius_meters=GEOFENCE_RADIUS_METERS
    )

    if not is_location_valid:
        return {
            "status": "failed",
            "reason": f"Clock-in failed. You must be within {GEOFENCE_RADIUS_METERS} meters of the office."
        }
    
    # --- 2. Face Recognition ---
    content = await file.read()
    live_descriptor = engine.extract_descriptor(content)
    if live_descriptor is None:
        return {"status": "failed", "reason": "No face detected"}

    session: Session = SessionLocal()
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()
    time_ist = now_ist.time().replace(microsecond=0)

    users = session.query(FaceUser).filter(FaceUser.face_user_emp_id == face_user_emp_id).all()
    if not users:
        session.close()
        return {"status": "failed", "reason": "User not found"}

    # Check user's shift for clockin
    emp_shift = session.query(EmpShift).filter(EmpShift.est_shift_abbrv == shift).first()
    if not emp_shift:
        session.close()
        return {"status": "failed", "reason": "Shift not found"}

    # Compare faces
    for user in users:
        db_desc = np.array(user.embedding)
        distance = np.linalg.norm(live_descriptor - db_desc)
        print(f"[LOG] Compared with {user.name} → Distance: {distance:.4f}")

        if distance < CLOCKIN_THRESHOLD:
            # --- CLOCK IN LOGIC START ---
            clockin_exists = (
                session.query(ClockInClockOut)
                .filter(
                    ClockInClockOut.cct_emp_id == int(face_user_emp_id),
                    ClockInClockOut.cct_date == today_ist,
                    ClockInClockOut.cct_clockin_time != None
                )
                .first()
            )
            if not clockin_exists:
                new_clockin = ClockInClockOut(
                    cct_emp_id=int(face_user_emp_id),
                    cct_date=today_ist,
                    cct_clockin_time=time_ist,
                    cct_shift_abbrv=shift,
                )
                session.add(new_clockin)
                session.commit()
            # --- CLOCK IN LOGIC END ---
            session.close()
            return {
                "status": "success",
                "user": user.name,
                "distance": round(distance, 4)
            }

    session.close()
    return {
        "status": "failed",
        "reason": "Face does not match logged-in user"
    }

@router.put("/clockout")
async def clockout(request: Request):
    """Clock-out endpoint"""
    data = await request.json()
    print("Raw body:", data)
    emp_id = data.get("emp_id")
    
    session: Session = SessionLocal()
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()
    time_ist = now_ist.time().replace(microsecond=0)
    
    try:
        # Find today's clock-in
        record = (
            session.query(ClockInClockOut)
            .filter(
                ClockInClockOut.cct_emp_id == emp_id,
                ClockInClockOut.cct_date == today_ist
            )
            .first()
        )
        if not record:
            session.close()
            return {"status": "failed", "error": "No clock-in found for today"}
        
        # Update clockout time
        record.cct_clockout_time = time_ist
        session.commit()
        session.close()
        return {"status": "success", "clockout_time": str(time_ist)}
    except Exception as e:
        session.rollback()
        session.close()
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
