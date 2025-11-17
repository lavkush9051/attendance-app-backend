from fastapi import APIRouter, Form, Body, Query, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any
import calendar
from app.dependencies import (
    get_current_user_emp_id, validate_admin_access, 
    get_attendance_service, get_clock_service, get_employee_service
)
from app.auth import get_current_user
from app.services.attendance_service import AttendanceService
from app.services.clock_service import ClockService
from app.services.employee_service import EmployeeService

router = APIRouter()

IST = ZoneInfo("Asia/Kolkata")

@router.get("/attendance-requests")
def get_all_attendance_requests(
    admin_emp_id: int = Depends(validate_admin_access),
    attendance_service: AttendanceService = Depends(get_attendance_service)
):
    """Get all attendance requests with employee information - Admin only"""
    print(f"[LOG] /attendance-requests called by admin {admin_emp_id}")
    try:
        # Use service to get admin requests (which includes employee info)
        attendance_requests = attendance_service.get_admin_requests(admin_emp_id)
        
        # Convert service response to frontend expected format
        formatted_requests = []
        for request in attendance_requests:
            request_dict = {
                "id": str(request.request_id),
                "emp_id": str(request.employee_id),
                "employee_name": request.employee_name,
                "emp_department": request.employee_department or "",
                "emp_designation": request.employee_designation or "",
                "date": request.request_date.isoformat(),
                "original_clock_in": "",  # Not available, would need to fetch from clock records
                "original_clock_out": "",  # Not available, would need to fetch from clock records
                "clock_in": request.clock_in.strftime("%H:%M") if request.clock_in else "",
                "clock_out": request.clock_out.strftime("%H:%M") if request.clock_out else "",
                "reason": request.reason or "",
                "type": "regularization",  # Default type
                "status": request.status.lower() if request.status else "pending",
                "l1_status": request.l1_status.lower() if request.l1_status else "pending",
                "l2_status": request.l2_status.lower() if request.l2_status else "pending",
                "applied_date": request.request_date.isoformat(),  # Using request_date as applied_date
                "approved_by": "",  # Not available in current schema
                "approved_date": "",  # Not available in current schema
                "rejection_reason": "",  # Not available in current schema
                "shift": request.shift or ""
            }
            formatted_requests.append(request_dict)
        
        print(f"[LOG] /attendance-requests returning {len(formatted_requests)} requests")
        return JSONResponse(content=formatted_requests)
    except Exception as e:
        print(f"[ERROR] /attendance-requests exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/regularization-requests/{emp_id}")
def get_attendance_regularization_requests(
    emp_id: int,
    admin: bool = Query(False),
    current_user_emp_id: int = Depends(get_current_user_emp_id),
    attendance_service: AttendanceService = Depends(get_attendance_service)
):
    """Get attendance regularization requests for employee or admin"""
    print(f"[LOG] /regularization-requests/{emp_id} called with admin={admin}, current_user={current_user_emp_id}")
    try:
        # Authorization check: users can only view their own requests unless they're admin
        print(f"[DEBUG] Authorization check: emp_id={emp_id}, current_user_emp_id={current_user_emp_id}, admin={admin}")
        
        if emp_id != current_user_emp_id and admin:
            # For admin view, we should validate through the admin_access dependency instead
            print(f"[ERROR] Authorization failed: admin view not allowed")
            raise HTTPException(
                status_code=403,
                detail="Use admin endpoints for cross-employee access"
            )
        elif emp_id != current_user_emp_id and not admin:
            print(f"[ERROR] Authorization failed: cross-employee access denied")
            raise HTTPException(
                status_code=403,
                detail="Access denied - can only view your own requests"
            )
        
        print(f"[DEBUG] Authorization passed, proceeding with admin={admin}")
        
        if not admin:
            # Employee view: get their own requests
            print(f"[DEBUG] Calling attendance_service.get_employee_requests({emp_id})")
            employee_requests = attendance_service.get_employee_requests(emp_id)
            print(f"[DEBUG] Raw employee_requests: {employee_requests}")
            print(f"[DEBUG] Number of requests: {len(employee_requests)}")
            print(f"[DEBUG] Type of first request: {type(employee_requests[0]) if employee_requests else 'None'}")
            
            # Convert to frontend expected format
            formatted_requests = []
            
            # If no requests found, return mock data for testing
            if not employee_requests:
                print(f"[DEBUG] No attendance requests found for employee {emp_id}, returning mock data")
                mock_data = [
                    {
                        "id": "1",
                        "emp_id": str(emp_id),
                        "employee_name": "Test Employee",
                        "date": "2024-10-07",
                        "original_clock_in": "09:00",
                        "original_clock_out": "18:00",
                        "clock_in": "09:15",
                        "clock_out": "18:30",
                        "reason": "Traffic delay",
                        "type": "regularization",
                        "status": "pending",
                        "l1_status": "pending",
                        "l2_status": "pending",
                        "applied_date": "2024-10-07",
                        "approved_by": "",
                        "approved_date": "",
                        "rejection_reason": "",
                        "shift": "General"
                    }
                ]
                print(f"[LOG] /regularization-requests/{emp_id} returning {len(mock_data)} mock requests for employee")
                return JSONResponse(content=mock_data)
            
            for i, request in enumerate(employee_requests):
                print(f"[DEBUG] Request {i}: {request}")
                print(f"[DEBUG] Request type: {type(request)}")
                if hasattr(request, '__dict__'):
                    print(f"[DEBUG] Request dict: {request.__dict__}")
                
                try:
                    request_dict = {
                        "id": str(getattr(request, 'request_id', '')),
                        "emp_id": str(getattr(request, 'employee_id', emp_id)),
                        "employee_name": getattr(request, 'employee_name', ''),
                        "date": getattr(request, 'request_date', '').isoformat() if hasattr(getattr(request, 'request_date', None), 'isoformat') else '',
                        "original_clock_in": "",  # Not available, would need to fetch from clock records
                        "original_clock_out": "",  # Not available, would need to fetch from clock records
                        "clock_in": getattr(request, 'clock_in', None).strftime("%H:%M") if getattr(request, 'clock_in', None) else "",
                        "clock_out": getattr(request, 'clock_out', None).strftime("%H:%M") if getattr(request, 'clock_out', None) else "",
                        "reason": getattr(request, 'reason', '') or "",
                        "type": "regularization",  # Default type
                        "status": (getattr(request, 'status', '') or 'pending').lower(),
                        "l1_status": (getattr(request, 'l1_status', '') or 'pending').lower(),
                        "l2_status": (getattr(request, 'l2_status', '') or 'pending').lower(),
                        "applied_date": getattr(request, 'applied_date', '').isoformat() if hasattr(getattr(request, 'applied_date', None), 'isoformat') else '',
                        "approved_by": "",  # Not available in current schema
                        "approved_date": "",  # Not available in current schema
                        "rejection_reason": "",  # Not available in current schema
                        "shift": getattr(request, 'shift', '') or ""
                    }
                    print(f"[DEBUG] Formatted request: {request_dict}")
                    formatted_requests.append(request_dict)
                except Exception as e:
                    print(f"[ERROR] Error formatting request {i}: {e}")
                    continue
            print(f"[LOG] /regularization-requests/{emp_id} returning {len(formatted_requests)} requests for employee")
            print(f"[DEBUG] Final formatted_requests content: {formatted_requests}")
            return JSONResponse(content=formatted_requests)
        else:
            # Admin view: get requests they need to approve
            admin_requests = attendance_service.get_admin_requests(emp_id)
            
            # Convert to frontend expected format
            formatted_requests = []
            for request in admin_requests:
                request_dict = {
                    "id": str(request.request_id),
                    "emp_id": str(request.employee_id),
                    "employee_name": request.employee_name,
                    "emp_department": request.employee_department or "",
                    "date": request.request_date.isoformat(),
                    "original_clock_in": "",  # Not available, would need to fetch from clock records
                    "original_clock_out": "",  # Not available, would need to fetch from clock records
                    "clock_in": request.clock_in.strftime("%H:%M") if request.clock_in else "",
                    "clock_out": request.clock_out.strftime("%H:%M") if request.clock_out else "",
                    "reason": request.reason or "",
                    "type": "regularization",  # Default type
                    "status": request.status.lower() if request.status else "pending",
                    "l1_status": request.l1_status.lower() if request.l1_status else "pending",
                    "l2_status": request.l2_status.lower() if request.l2_status else "pending",
                    "applied_date": request.applied_date.isoformat() if request.applied_date else "",
                    "approved_by": "",  # Not available in current schema
                    "approved_date": "",  # Not available in current schema
                    "rejection_reason": "",  # Not available in current schema
                    "shift": request.shift or ""
                }
                formatted_requests.append(request_dict)
            
            return JSONResponse(content=formatted_requests)
    except Exception as e:
        print(f"[ERROR] Exception in /regularization-requests/{emp_id}: {str(e)}")
        print(f"[ERROR] Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/attendance-regularization")
def create_attendance_request(
    emp_id: int = Form(...),
    date: str = Form(...),          # 'YYYY-MM-DD'
    clock_in: str = Form(...),      # 'HH:MM' (24-hour)
    clock_out: str = Form(...),     # 'HH:MM'
    reason: str = Form(...),
    shift: str = Form(...),
    current_user_emp_id: int = Depends(get_current_user_emp_id),
    attendance_service: AttendanceService = Depends(get_attendance_service)
):
    """Create an attendance regularization request"""
    print(f"[LOG] /attendance-regularization called with emp_id={emp_id}, date={date}, clock_in={clock_in}, clock_out={clock_out}, current_user={current_user_emp_id}")
    try:
        # Authorization check: users can only create requests for themselves
        if emp_id != current_user_emp_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied - can only create requests for yourself"
            )
        
        # Parse the form data
        att_date = datetime.strptime(date, "%Y-%m-%d").date()
        clock_in_time = datetime.strptime(clock_in, "%H:%M").time()
        clock_out_time = datetime.strptime(clock_out, "%H:%M").time()
        
        # Create service request
        from app.schemas.attendance import AttendanceRegularizationCreate
        regularization_request = AttendanceRegularizationCreate(
            request_date=att_date,
            clock_in_time=clock_in_time,
            clock_out_time=clock_out_time,
            reason=reason,
            shift=shift
        )
        
        # Use service to create the request
        response = attendance_service.create_regularization_request(
            regularization_request, emp_id
        )
        
        # Service returns AttendanceRequestResponse directly
        result = {"status": "success", "art_id": response.request_id}
        print(f"[LOG] /attendance-regularization success: {result}")
        return result
            
    except Exception as e:
        print(f"[ERROR] /attendance-regularization exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/attendance-request/action")
async def attendance_action(
    attendance_request_id: int = Body(...),
    action: str = Body(...),          # "approve" or "reject"
    admin_id: int = Body(...),
    attendance_service: AttendanceService = Depends(get_attendance_service)
):
    """
    Acts on an attendance regularization request at either L1 or L2 level, based on the caller (admin_id).
    Rules:
      - If admin is L1 (req.art_l1_id == admin_id): can approve/reject anytime.
      - If admin is L2 (req.art_l2_id == admin_id): can act ONLY AFTER L1 is Approved.
    """
    print(f"[LOG] /attendance-request/action called with request_id={attendance_request_id}, action={action}, admin_id={admin_id}")
    try:
        # Create service request
        from app.schemas.attendance import AttendanceStatusUpdate
        status_update = AttendanceStatusUpdate(
            status=action,  # "approve" or "reject"
            manager_id=admin_id
        )
        
        # Use service to update request status
        response = attendance_service.update_request_status(
            attendance_request_id, status_update, admin_id
        )
        
        # Service returns AttendanceRequestDetailResponse directly
        result = {"status": "success", "message": f"Request {action}d successfully"}
        print(f"[LOG] /attendance-request/action success: {result}")
        return JSONResponse(content=result)
            
    except Exception as e:
        error_result = {"status": "failed", "error": str(e)}
        print(f"[ERROR] /attendance-request/action exception: {error_result}")
        return JSONResponse(status_code=500, content=error_result)

@router.delete("/attendance-regularization/{request_id}")
def delete_attendance_regularization_request(
    request_id: int,
    request: Request,
    current_user_emp_id: int = Depends(get_current_user_emp_id),
    attendance_service: AttendanceService = Depends(get_attendance_service)
):
    """Cancel (delete) a pending attendance regularization request owned by the user.
    Only allowed if status is Pending and the requester is the owner.
    """
    print(f"[LOG] DELETE /attendance-regularization/{request_id} called by emp_id={current_user_emp_id}")
    try:
        # Debug incoming headers to verify CORS / credential behavior
        from fastapi import Request
        # Inject request via dependency-less approach using global (FastAPI provides it via context) - fallback
        # Proper way: accept Request as parameter; updating signature for better diagnostics
        # Log request headers for CORS diagnostics
        print(f"[CANCEL DEBUG] Origin: {request.headers.get('origin')}")
        print(f"[CANCEL DEBUG] Authorization present: {'authorization' in request.headers}")
        print(f"[CANCEL DEBUG] Cookie present: {bool(request.headers.get('cookie'))}")
        # Service layer enforces ownership and Pending status
        success = attendance_service.delete_request(request_id, current_user_emp_id)
        if not success:
            raise HTTPException(status_code=404, detail="Request not found or could not be deleted")
        result = {"status": "success", "message": "Request cancelled"}
        print(f"[LOG] DELETE /attendance-regularization/{request_id} success: {result}")
        return JSONResponse(content=result)
    except HTTPException as he:
        print(f"[ERROR] DELETE /attendance-regularization/{request_id} HTTPException: {he.detail}")
        raise
    except Exception as e:
        print(f"[ERROR] DELETE /attendance-regularization/{request_id} exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/attendance")
def get_attendance(
    emp_id: int = Query(...),
    start: str = Query(...),
    end: str = Query(...),
    current_user_emp_id: int = Depends(get_current_user_emp_id),
    clock_service: ClockService = Depends(get_clock_service),
    employee_service: EmployeeService = Depends(get_employee_service)
):
    """Get attendance summary for an employee within a date range"""
    print(f"[LOG] /attendance called with emp_id={emp_id}, start={start}, end={end}, current_user={current_user_emp_id}")
    try:
        # Authorization check: users can only view their own attendance unless they're admin
        if emp_id != current_user_emp_id:
            # Check if current user is admin
            current_emp = employee_service.get_employee_by_id(current_user_emp_id)
            if not current_emp or not (current_emp.emp_designation and 
                                      any(role in current_emp.emp_designation.lower() 
                                          for role in ['manager', 'lead', 'head', 'director', 'admin'])):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied - can only view your own attendance records"
                )
        
        # Parse date strings
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
        
        # For "This month" view, limit to current month only (not the full requested range)
        today = date.today()
        current_month_start = date(today.year, today.month, 1)
        
        # If the request spans multiple months and includes current month, focus on current month
        if (end_date.month != start_date.month or end_date.year != start_date.year) and \
           (current_month_start >= start_date and current_month_start <= end_date):
            print(f"[DEBUG] Multi-month request detected, focusing on current month: {current_month_start} to {today}")
            start_date = current_month_start
            end_date = min(end_date, today)  # Don't count future dates
        
        # Use clock service to get attendance records
        records = clock_service.get_employee_attendance_records(
            emp_id, start_date, end_date
        )
        #print("[Debug] Records fetched:", records)
        present_days = []
        total_working_mins = 0
        total_late_mins = 0
        late_standard = datetime.strptime("09:00", "%H:%M").time()
        
        for rec in records:
            # Format clockin/clockout as string
            clockin_str = rec.clockin_time.strftime("%I:%M %p") if rec.clockin_time else "-"
            clockout_str = rec.clockout_time.strftime("%I:%M %p") if rec.clockout_time else "-"
            present_days.append({
                "date": rec.date.strftime("%Y-%m-%d"),
                "clockIn": clockin_str,
                "clockOut": clockout_str,
                "shift": rec.shift or "-"
            })
            
            # Average working hours
            if rec.clockin_time and rec.clockout_time:
                t1 = datetime.combine(datetime.today(), rec.clockin_time)
                t2 = datetime.combine(datetime.today(), rec.clockout_time)
                total_working_mins += max(0, int((t2 - t1).total_seconds() / 60))
                
            # Average late by
            if rec.clockin_time:
                late = (
                    datetime.combine(datetime.today(), rec.clockin_time) -
                    datetime.combine(datetime.today(), late_standard)
                ).total_seconds() / 60
                total_late_mins += max(0, late)

        # Calculate working days within the requested date range (not entire month)
        num_present = len(present_days)
        total_working = 0
        
        # Count working days (Mon-Fri) between start_date and end_date
        print(f"[DEBUG] Calculating working days from {start_date} to {end_date}")
        current_date = start_date
        while current_date <= end_date:
            weekday = current_date.weekday()
            is_working_day = weekday < 5  # Monday=0, Friday=4 (exclude Sat/Sun)
            #print(f"[DEBUG] Date: {current_date}, Weekday: {weekday}, IsWorkingDay: {is_working_day}")
            if is_working_day:
                total_working += 1
            current_date += timedelta(days=1)
        
        absent = total_working - num_present
        #print(f"[DEBUG] Final calculation: total_working={total_working}, num_present={num_present}, absent={absent}")

        average_working = "-"
        average_late = "-"
        if num_present > 0:
            avg_mins = total_working_mins / num_present
            h, m = int(avg_mins // 60), int(avg_mins % 60)
            average_working = f"{h}h {m}m"
            avg_late = total_late_mins / num_present
            if avg_late < 1:
                average_late = "On Time"
            else:
                lh, lm = int(avg_late // 60), int(avg_late % 60)
                average_late = f"{lh}h {lm}m"

        # Get shift details from employee table
        # Get shift details from employee service
        employee = employee_service.get_employee_by_id(emp_id)
        shift = getattr(employee, "emp_shift", "-") if employee else "-"

        response_data = {
            "attendance": present_days,
            "holidays": [],  # You can fill this if you have holiday table
            "absent": absent,
            "average_working": average_working,
            "average_late": average_late,
            "shift": shift
        }
        print(f"[LOG] /attendance returning: {len(present_days)} attendance records, absent={absent}")
        return response_data
    except Exception as e:
        print(f"[ERROR] /attendance exception: {str(e)}")
        return {"error": str(e)}
