from fastapi import APIRouter, Form, Body, Query, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
import os
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.storage import save_upload_to_disk
from app.config import UPLOAD_ROOT
from app.database import SessionLocal, get_db
from app.models import LeaveRequest, Employee, LeaveBalance, LeaveLedger, LeaveAttachment
from app.dependencies import (
    get_current_user_emp_id, validate_admin_access,
    get_leave_service, get_employee_service
)
from app.auth import get_current_user
from app.services.leave_service import LeaveService
from app.services.employee_service import EmployeeService

router = APIRouter()

ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}

# Map your request leave type → LeaveBalance column name
LEAVE_COL_MAP = {
    "Casual Leave": "lt_casual_leave",
    "Earned Leave": "lt_earned_leave",
    "Half Pay Leave": "lt_half_pay_leave",
    "Medical Leave": "lt_medical_leave",
    "Special Leave": "lt_special_leave",
    "Child Care Leave": "lt_child_care_leave",
    "Parental Leave": "lt_parental_leave",
    "Commuted Leave": "lt_commuted_leave",
}

@router.get("/leave-types")
def get_leave_types(
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Get all available leave types"""
    print(f"[LOG] /leave-types called by user {current_emp_id}")
    try:
        # Return standard leave types - you can make this dynamic if needed
        leave_types = [
            {"id": "1", "name": "Casual Leave", "max_days": 12, "carry_forward": True, "description": "Casual Leave"},
            {"id": "2", "name": "Earned Leave", "max_days": 30, "carry_forward": True, "description": "Earned Leave"},
            {"id": "3", "name": "Medical Leave", "max_days": 15, "carry_forward": False, "description": "Medical Leave"},
            {"id": "4", "name": "Half Pay Leave", "max_days": 20, "carry_forward": False, "description": "Half Pay Leave"}
        ]
        print(f"[LOG] /leave-types returning {len(leave_types)} leave types")
        return JSONResponse(content=leave_types)
    except Exception as e:
        print(f"[ERROR] /leave-types exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leave-requests") 
def get_all_leave_requests(
    admin_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    leave_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Get leave requests for admin review"""
    print(f"[LOG] /leave-requests called by admin {current_emp_id} with filters: admin_id={admin_id}, status={status}")
    try:
        # Use admin_id from query or current user
        admin_emp_id = int(admin_id) if admin_id else current_emp_id
        
        # Use service to get admin leave requests (where user is L1 or L2 manager)
        admin_requests = leave_service.get_admin_leave_requests(admin_emp_id)
        
        # Convert service response to frontend expected format
        formatted_requests = []
        for request in admin_requests:
            request_dict = {
                "id": str(request.request_id),
                "emp_id": str(request.employee_id),
                "employee_name": request.employee_name,
                "leave_type_id": "1",  # Default or map from leave_type
                "leave_type_name": request.leave_type,
                "start_date": request.from_date.isoformat(),
                "end_date": request.to_date.isoformat(),
                "days": (request.to_date - request.from_date).days + 1,
                "reason": request.reason,
                "status": request.status.lower(),
                "applied_date": str(request.applied_date) if request.applied_date else "",
                "approved_by": "",
                "approved_date": "",
                "rejection_reason": "",
                "l1_status": request.l1_status.lower(),
                "l2_status": request.l2_status.lower(),
                "attachment": None,
                "remarks": request.remarks
                
            }
            formatted_requests.append(request_dict)
        
        print(f"[LOG] /leave-requests returning {len(formatted_requests)} admin requests")
        return JSONResponse(content=formatted_requests)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leave-requests/{emp_id}")
def get_leave_requests(
    emp_id: str,
    admin: bool = Query(False),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Get leave requests for employee or admin view"""
    print(f"[LOG] /leave-requests/{emp_id} called by user {current_emp_id}, admin={admin}, status={status}")
    try:
        emp_id_int = int(emp_id)
        if not admin:
            # Employee view: get their own leave requests
            employee_requests = leave_service.get_employee_leave_requests(emp_id_int)
            
            if status:
                # exclude  if employee_requests.status.lower() = 'rejected' or 'cancelled'
                #employee_requests = [req for req in employee_requests if req.status.lower() != 'rejected' and req.status.lower() != 'cancelled']
                employee_requests = [req for req in employee_requests if req.status.lower() == 'approved']
                print(f"[DEBUG] Employee requests from service: {len(employee_requests)}")    
            
            # Convert to frontend expected format
            formatted_requests = []
            for request in employee_requests:
                request_dict = {
                    "id": str(request.request_id),
                    "emp_id": str(request.employee_id),
                    "employee_name": request.employee_name,
                    "leave_type_id": "1",  # Default or map from leave_type
                    "leave_type_name": request.leave_type,
                    "start_date": request.from_date.isoformat(),
                    "end_date": request.to_date.isoformat(),
                    "days": (request.to_date - request.from_date).days + 1,
                    "reason": request.reason,
                    "status": request.status.lower(),
                    "applied_date": str(request.applied_date) if request.applied_date else str(request.from_date),
                    "approved_by": "",
                    "approved_date": "",
                    "rejection_reason": "",
                    "l1_status": request.l1_status.lower(),
                    "l2_status": request.l2_status.lower(),
                    "attachment": None,
                    "remarks": request.remarks
                }
                formatted_requests.append(request_dict)
            
            print(f"[LOG] /leave-requests/{emp_id} returning {len(formatted_requests)} employee requests")
            return JSONResponse(content=formatted_requests)
        else:
            # Admin view: get requests they need to approve
            admin_requests = leave_service.get_admin_leave_requests(emp_id_int)
            print(f"[DEBUG] Admin requests from service: {len(admin_requests)}")
            
            # Convert to frontend expected format
            formatted_requests = []
            for i, request in enumerate(admin_requests):
                #print(f"[DEBUG] Admin request {i}: remarks='{getattr(request, 'remarks', 'NOT FOUND')}'")
                request_dict = {
                    "id": str(request.request_id),
                    "emp_id": str(request.employee_id),
                    "employee_name": request.employee_name,
                    "leave_type_id": "1",  # Default or map from leave_type
                    "leave_type_name": request.leave_type,
                    "start_date": request.from_date.isoformat(),
                    "end_date": request.to_date.isoformat(),
                    "days": (request.to_date - request.from_date).days + 1,
                    "reason": request.reason,
                    "status": request.status.lower(),
                    "applied_date": str(request.applied_date) if request.applied_date else str(request.from_date),
                    "approved_by": "",
                    "approved_date": "",
                    "rejection_reason": "",
                    "l1_status": request.l1_status.lower(),
                    "l2_status": request.l2_status.lower(),
                    "attachment": None,
                    "remarks": getattr(request, 'remarks', '') or "",
                    "l1_id": getattr(request, 'leave_req_l1_id', None),
                    "l2_id": getattr(request, 'leave_req_l2_id', None),
                }
                formatted_requests.append(request_dict)
            
            print(f"[LOG] /leave-requests/{emp_id} admin view returning {len(formatted_requests)} requests")
            return JSONResponse(content=formatted_requests)
    except ValueError:
        print(f"[ERROR] /leave-requests/{emp_id} invalid employee ID format")
        raise HTTPException(status_code=400, detail="Invalid employee ID format")
    except Exception as e:
        print(f"[ERROR] /leave-requests/{emp_id} exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# @router.get("/leave-balance/snapshot")
# def get_leave_balance_snapshot(
#     emp_id: str = Query(...),
#     current_emp_id: int = Depends(get_current_user_emp_id),
#     leave_service: LeaveService = Depends(get_leave_service)
# ):
#     """Get leave balance snapshot for employee"""
#     print(f"[LOG] /leave-balance/snapshot called for emp_id={emp_id} by user {current_emp_id}")
#     try:
#         emp_id_int = int(emp_id)
        
#         # Get actual leave balance data from service
#         balance_result = leave_service.get_employee_balance_snapshot(emp_id_int, current_emp_id)
#         print(f"[DEBUG] Leave balance snapshot from service: {balance_result}")
        
#         # Transform the service response to match frontend expectations
#         types_list = []
#         total_accrued = 0
#         total_held = 0
#         total_committed = 0
#         total_available = 0
        
#         if 'balances' in balance_result:
#             for leave_type, balance_info in balance_result['balances'].items():
#                 # Extract values with defaults  
#                 accrued = balance_info.get('accrued', 0)
#                 held = balance_info.get('held', 0)
#                 committed = balance_info.get('committed', 0)
#                 available = balance_info.get('available', 0)
                
#                 types_list.append({
#                     "type": leave_type,
#                     "accrued": accrued,
#                     "held": held,
#                     "committed": committed,
#                     "available": available
#                 })
                
#                 # Calculate totals
#                 total_accrued += accrued
#                 total_held += held
#                 total_committed += committed
#                 total_available += available
        
#         # Format response as expected by frontend
#         balance_data = {
#             "emp_id": str(emp_id_int),
#             "types": types_list,
#             "totals": {
#                 "accrued": total_accrued,
#                 "held": total_held,
#                 "committed": total_committed,
#                 "available": total_available
#             }
#         }
        
#         print(f"[LOG] /leave-balance/snapshot returning balance for emp {emp_id}: {balance_data}")
#         return JSONResponse(content=balance_data)
#     except ValueError:
#         print(f"[ERROR] /leave-balance/snapshot invalid employee ID format: {emp_id}")
#         raise HTTPException(status_code=400, detail="Invalid employee ID format")
#     except Exception as e:
#         print(f"[ERROR] /leave-balance/snapshot exception: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


from fastapi import Query, Depends, HTTPException
from fastapi.responses import JSONResponse
from copy import deepcopy
### new function for leave balance snapshot with business rules
@router.get("/leave-balance/snapshot")
def get_leave_balance_snapshot(
    emp_id: str = Query(...),
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)
):
    print(f"[LOG] /leave-balance/snapshot called for emp_id={emp_id} by user {current_emp_id}")

    try:
        emp_id_int = int(emp_id)

        # STEP 1 — Fetch original service data
        balance_result = leave_service.get_employee_balance_snapshot(emp_id_int, current_emp_id)
        print(f"[DEBUG] Raw balance snapshot from service: {balance_result}")

        if not balance_result or "balances" not in balance_result:
            raise HTTPException(status_code=404, detail="No leave balance data found.")

        # STEP 2 — Deep copy so we can modify safely
        balance_result_modified = deepcopy(balance_result)
        balances = balance_result_modified.get("balances", {})

        # STEP 3 — Function to find keys independent of case/spacing
        def find_key(dictionary, target_name):
            target = target_name.lower().strip()
            for key in dictionary.keys():
                if key.lower().strip() == target:
                    return key
            return None

        # Locate keys safely
        half_pay_key = find_key(balances, "Half Pay Leave")
        commuted_key = find_key(balances, "Commuted Leave")

        # STEP 4 — Apply business rule (deduct Commuted Leave committed & held)
        if half_pay_key and commuted_key:
            half_pay = balances[half_pay_key]
            commuted = balances[commuted_key]

            hp_available = half_pay.get("available", 0)
            com_committed = commuted.get("committed", 0)
            com_held = commuted.get("held", 0)

            updated_hp_available = hp_available - com_committed*2 - com_held*2
            updated_hp_available = max(updated_hp_available, 0)  # avoid negative

            balances[half_pay_key]["available"] = updated_hp_available

            print(f"[DEBUG] Updated Half Pay Leave available: {updated_hp_available}")
        else:
            print(f"[WARN] Key not found: Half Pay Leave or Commuted Leave. No deduction applied.")

        # STEP 5 — Build frontend response format
        types_list = []
        total_accrued = 0
        total_held = 0
        total_committed = 0
        total_available = 0

        for leave_type, info in balances.items():
            accrued = info.get("accrued", 0)
            held = info.get("held", 0)
            committed = info.get("committed", 0)
            available = info.get("available", 0)

            types_list.append({
                "type": leave_type,
                "accrued": accrued,
                "held": held,
                "committed": committed,
                "available": available
            })

            total_accrued += accrued
            total_held += held
            total_committed += committed
            total_available += available

        # STEP 6 — Final response object
        balance_data = {
            "emp_id": str(emp_id_int),
            "types": types_list,
            "totals": {
                "accrued": total_accrued,
                "held": total_held,
                "committed": total_committed,
                "available": total_available
            }
        }

        print(f"[LOG] /leave-balance/snapshot returning: {balance_data}")
        return JSONResponse(content=balance_data)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid employee ID format")
    except Exception as e:
        print(f"[ERROR] /leave-balance/snapshot exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leave-request")
async def create_leave_request(
    emp_id: int = Form(...),
    leave_type: str = Form(...),
    leave_from_dt: str = Form(...),
    leave_to_dt: str = Form(...),
    leave_reason: str = Form(...),
    leave_applied_dt: str = Form(...),
    immediate_reporting_officer: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)    
):
    """Create a new leave request"""
    print(f"[LOG] /leave-request called by user {current_emp_id} for emp_id={emp_id}, leave_type={leave_type}, from={leave_from_dt}, to={leave_to_dt},immediate_reporting_officer={immediate_reporting_officer}")
    
    session: Session = SessionLocal()
    try:
        # Parse dates
        from datetime import datetime
        from_date = datetime.strptime(leave_from_dt, "%Y-%m-%d").date()
        to_date = datetime.strptime(leave_to_dt, "%Y-%m-%d").date()
        
        # Create leave request schema object
        from app.schemas.leaves import LeaveRequestCreate
        leave_request = LeaveRequestCreate(
            from_date=from_date,
            to_date=to_date,
            leave_type=leave_type,
            reason=leave_reason,
            immediate_reporting_officer=immediate_reporting_officer
        )
        
        # Create leave request through service
        result = leave_service.create_leave_request(leave_request, emp_id)
        
        # Handle file attachments if any
        if files and any(f.filename for f in files):
            print(f"[LOG] Processing {len(files)} file attachments for leave request {result.request_id}")
            for f in files:
                if not f.filename:
                    continue
                if f.content_type not in ALLOWED_MIME:
                    print(f"[WARNING] Skipping unsupported file type: {f.content_type}")
                    continue
                
                # Save file to disk
                rel_path, size, mime = await save_upload_to_disk(
                    f, UPLOAD_ROOT, subdir=f"leave/{result.request_id}"
                )
                
                # Create attachment record
                session.add(LeaveAttachment(
                    la_leave_req_id=result.request_id,
                    la_filename=f.filename,
                    la_mime_type=mime,
                    la_size_bytes=size,
                    la_disk_path=rel_path,
                    la_uploaded_by=current_emp_id,
                ))
            
            session.commit()
            print(f"[LOG] Successfully saved attachments for leave request {result.request_id}")
        
        print(f"[LOG] /leave-request result: {result}")
        return result
        
    except HTTPException:
        session.rollback()
        raise
    except ValueError as e:
        # Date parsing errors
        session.rollback()
        print(f"[WARNING] /leave-request validation issue: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        error_msg = str(e)
        
        # Check if it's a validation error (use 400) or server error (use 500)
        validation_keywords = [
            "overlaps", "balance", "cannot", "insufficient", "not found", 
            "past dates", "after to date", "already", "required"
        ]
        is_validation = any(keyword in error_msg.lower() for keyword in validation_keywords)
        
        if is_validation:
            print(f"[INFO] /leave-request validation message: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            print(f"[ERROR] /leave-request exception: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
    finally:
        session.close()

@router.put("/leave-request/action")
def leave_action(
    leave_req_id: int = Body(...),
    action: str = Body(...),      # "approve", "reject", or "cancel"
    admin_id: int = Body(...),
    comments: Optional[str] = Body(None),
    remarks: Optional[str] = Body(None),
    next_reporting_officer: Optional[str] = Body(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Handle leave request approval/rejection/cancellation with ledger operations"""
    print("[LOG] /leave-request/action called by user {current_emp_id} for request {leave_req_id}, action={action}")
    if(next_reporting_officer == "" or next_reporting_officer == None):
        next_reporting_officer = None
    else:
        next_reporting_officer = int(next_reporting_officer)
    try:
        # Get the leave request to determine L1/L2 roles
        from sqlalchemy.orm import Session
        from app.database import get_db
        db = next(get_db())
        
        leave_req = db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == leave_req_id).first()
        if not leave_req:
            raise HTTPException(status_code=404, detail="Leave request not found")
        
        # Use either remarks or comments field
        final_remarks = remarks or comments
        
        # Determine which approval method to call based on user role and action
        if action.lower() == "approve":
            # Check if user is L1 manager
            if leave_req.leave_req_l1_id == current_emp_id:
                result = leave_service.l1_approve_leave_request(leave_req_id, current_emp_id, final_remarks, next_reporting_officer)
            # Check if user is L2 manager
            elif leave_req.leave_req_l2_id == current_emp_id:
                result = leave_service.l2_approve_leave_request(leave_req_id, current_emp_id, final_remarks)
            else:
                raise HTTPException(status_code=403, detail="Not authorized to approve this request")
        
        elif action.lower() == "reject":
            # Both L1 and L2 can reject
            if current_emp_id in [leave_req.leave_req_l1_id, leave_req.leave_req_l2_id]:
                result = leave_service.reject_leave_request(leave_req_id, current_emp_id, final_remarks or "Rejected")
            else:
                raise HTTPException(status_code=403, detail="Not authorized to reject this request")
        
        elif action.lower() == "cancel":
            # Check if user is the employee who created the request
            if leave_req.leave_req_emp_id == current_emp_id:
                result = leave_service.cancel_leave_request(leave_req_id, current_emp_id, final_remarks or "Cancelled by employee")
            # Check if user is L1 manager
            elif leave_req.leave_req_l1_id == current_emp_id:
                result = leave_service.l1_cancel_leave_request(leave_req_id, current_emp_id, final_remarks)
            # Check if user is L2 manager
            elif leave_req.leave_req_l2_id == current_emp_id:
                result = leave_service.l2_cancel_leave_request(leave_req_id, current_emp_id, final_remarks)
            else:
                raise HTTPException(status_code=403, detail="Not authorized to cancel this request")
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'approve', 'reject', or 'cancel'")
        
        db.close()
        print(f"[LOG] /leave-request/action result: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] /leave-request/action exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/leave-requests/{leave_req_id}")
def delete_leave_request(
    leave_req_id: str,
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Delete a leave request"""
    print(f"[LOG] /leave-requests/{leave_req_id} DELETE called by user {current_emp_id}")
    try:
        leave_req_id_int = int(leave_req_id)
        result = leave_service.delete_leave_request(leave_req_id_int)
        print(f"[LOG] /leave-requests/{leave_req_id} DELETE result: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# @router.get("/leave-balance")
# def get_leave_balance(
#     emp_id: int = Query(...),
#     current_emp_id: int = Depends(get_current_user_emp_id),
#     leave_service: LeaveService = Depends(get_leave_service)
# ):
#     """Get basic leave balance for an employee"""
#     try:
#         # Authorization check: users can only view their own leave balance
#         if emp_id != current_emp_id:
#             raise HTTPException(
#                 status_code=403,
#                 detail="Access denied - can only view your own leave balance"
#             )
        
#         balance_data = leave_service.get_employee_leave_balance(emp_id)
#         return {"status": "success", "data": balance_data}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.get("/leave-types")
def get_leave_types(
    current_emp_id: int = Depends(get_current_user_emp_id),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Get all available leave types"""
    try:
        leave_types = leave_service.get_leave_types()
        return {"leave_types": leave_types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/leave-requests/{leave_req_id}/attachments")
async def upload_attachments(
    leave_req_id: int, 
    files: List[UploadFile] = File(...), 
    uploader_emp_id: int = Form(...),
    current_emp_id: int = Depends(get_current_user_emp_id)
):
    """Upload attachments for a leave request"""
    
    # Authorization check: users can only upload attachments for their own requests
    if uploader_emp_id != current_emp_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied - can only upload attachments for your own leave requests"
        )
    
    session: Session = SessionLocal()
    try:
        # Verify uploader is the request owner
        for f in files:
            if not f.filename:
                continue
            if f.content_type not in ALLOWED_MIME:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {f.content_type}")
            rel_path, size, mime = await save_upload_to_disk(
                f, UPLOAD_ROOT, subdir=f"leave/{leave_req_id}"
            )
            session.add(LeaveAttachment(
                la_leave_req_id=leave_req_id,
                la_filename=f.filename,
                la_mime_type=mime,
                la_size_bytes=size,
                la_disk_path=rel_path,
                la_uploaded_by=uploader_emp_id,
            ))
        session.commit()
        return {"status": "success"}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@router.get("/leave-request/{leave_req_id}/attachment/meta")
def get_leave_attachment_meta(
    leave_req_id: int,
    actor_emp_id: Optional[int] = Query(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    db: Session = Depends(get_db),
):
    """Get metadata for leave request attachments"""
    req = db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == leave_req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")

    # Authorization check: only employee, L1, or L2 manager can access attachments
    allowed = { req.leave_req_emp_id, getattr(req, "leave_req_l1_id", None), getattr(req, "leave_req_l2_id", None) }
    if current_emp_id not in allowed:
        raise HTTPException(status_code=403, detail="Not authorized to access this attachment")

    atts = (
        db.query(LeaveAttachment)
        .filter(LeaveAttachment.la_leave_req_id == leave_req_id)
        .order_by(LeaveAttachment.la_id.asc())
        .all()
    )
    if not atts:
        return {"has_attachment": False, "items": []}

    qs = f"?actor_emp_id={actor_emp_id}" if actor_emp_id is not None else ""
    items = [{
        "id": a.la_id,
        "original_name": a.la_filename,
        "mime_type": a.la_mime_type,
        "size_bytes": a.la_size_bytes,
        "url": f"/api/leave-request/{leave_req_id}/attachment{qs}",
    } for a in atts]

    return {"has_attachment": True, "items": items}

@router.get("/leave-request/{leave_req_id}/attachment")
def download_leave_attachment(
    leave_req_id: int,
    actor_emp_id: Optional[int] = Query(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    db: Session = Depends(get_db),
):
    """Download leave request attachment"""
    print(f"[ATTACHMENT][GET] leave_req_id={leave_req_id}, actor_emp_id={actor_emp_id}")

    req = db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == leave_req_id).first()
    if not req:
        print(f"[ATTACHMENT] leave request not found")
        raise HTTPException(status_code=404, detail="Leave request not found")

    # Authorization check: only employee, L1, or L2 manager can access attachments
    allowed = {
        req.leave_req_emp_id,
        getattr(req, "leave_req_l1_id", None),
        getattr(req, "leave_req_l2_id", None),
    }
    print(f"[ATTACHMENT] allowed={allowed}, current_user={current_emp_id}")
    if current_emp_id not in allowed:
        raise HTTPException(status_code=403, detail="Not authorized to access this attachment")

    # fetch first attachment for this request
    att = (
        db.query(LeaveAttachment)
        .filter(LeaveAttachment.la_leave_req_id == leave_req_id)
        .order_by(LeaveAttachment.la_id.asc())
        .first()
    )
    if not att:
        print(f"[ATTACHMENT] no attachment rows for leave_req_id={leave_req_id}")
        raise HTTPException(status_code=404, detail="No attachment on this leave request")

    print(f"[ATTACHMENT] la_id={att.la_id}")
    print(f"[ATTACHMENT] db.rel_path={att.la_disk_path!r}")

    full_path = resolve_attachment_path(att.la_disk_path)
    print(f"[ATTACHMENT] resolved_full_path={full_path}")
    print(f"[ATTACHMENT] exists={full_path.is_file()} UPLOAD_ROOT={UPLOAD_ROOT}")

    if not full_path.is_file():
        # Optional: debug directory contents
        parent = full_path.parent
        listing = ", ".join(os.listdir(parent)) if parent.exists() else "<no dir>"
        print(f"[ATTACHMENT] missing file. dir={parent} contents={listing}")
        raise HTTPException(status_code=404, detail="Attachment file not found")

    filename = att.la_filename or full_path.name
    mime = att.la_mime_type or "application/octet-stream"
    print(f"[ATTACHMENT] serving {filename} ({mime})")
    return FileResponse(str(full_path), media_type=mime, filename=filename)

# Helper functions
def business_days_inclusive(start_dt: datetime.date, end_dt: datetime.date) -> float:
    """Simple version: count Mon–Fri only. No holiday table used here."""
    if end_dt < start_dt:
        return 0
    days = 0
    cur = start_dt
    one = timedelta(days=1)
    while cur <= end_dt:
        if cur.weekday() < 5:  # 0=Mon ... 4=Fri
            days += 1
        cur += one
    return float(days)

def get_accrued(db: Session, emp_id: int, leave_type: str) -> float:
    """Get accrued leave balance for employee and leave type"""
    col = LEAVE_COL_MAP.get(leave_type)
    if not col:
        return 0.0
    row = db.query(LeaveBalance).filter(LeaveBalance.lt_emp_id == emp_id).one_or_none()
    if not row:
        return 0.0
    return float(getattr(row, col) or 0)

def sum_ledger(db: Session, emp_id: int, leave_type: str, action: str) -> float:
    """Sum ledger entries for specific action"""
    total = db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0))\
              .filter(LeaveLedger.ll_emp_id == emp_id,
                      LeaveLedger.ll_leave_type == leave_type,
                      LeaveLedger.ll_action == action)\
              .scalar()
    return float(total or 0.0)

def get_balance_snapshot(db: Session, emp_id: int, leave_type: str) -> dict:
    """Get current balance snapshot for leave type"""
    accrued = get_accrued(db, emp_id, leave_type)
    held = sum_ledger(db, emp_id, leave_type, "HOLD") - sum_ledger(db, emp_id, leave_type, "RELEASE")
    committed = sum_ledger(db, emp_id, leave_type, "COMMIT")
    available = accrued - committed - max(0.0, held)
    return {"accrued": accrued, "held": max(0.0, held), "committed": committed, "available": available}

# Removed helper functions - moved to service layer via repository pattern

# @router.get("/balance-snapshot/{emp_id}")
# def get_employee_balance_snapshot(
#     emp_id: int,
#     leave_type: Optional[str] = Query(None, description="Leave type filter"),
#     current_emp_id: int = Depends(get_current_user_emp_id),
#     leave_service: LeaveService = Depends(get_leave_service)
# ):
#     """
#     Get balance snapshot for employee showing accrued, held, committed, and available balances
#     """
#     try:
#         result = leave_service.get_employee_balance_snapshot(emp_id, current_emp_id, leave_type)
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error retrieving balance snapshot: {str(e)}")

@router.post("/approve/l1/{req_id}")
def l1_approve_leave(
    req_id: int,
    remarks: Optional[str] = Body(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    db: Session = Depends(get_db),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """L1 manager approves leave request"""
    try:
        result = leave_service.l1_approve_leave_request(req_id, current_emp_id, remarks)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/approve/l2/{req_id}")
def l2_approve_leave(
    req_id: int,
    remarks: Optional[str] = Body(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    db: Session = Depends(get_db),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """L2 manager approves leave request"""
    try:
        result = leave_service.l2_approve_leave_request(req_id, current_emp_id, remarks)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reject/{req_id}")
def reject_leave_request(
    req_id: int,
    remarks: str = Body(..., embed=True),
    current_emp_id: int = Depends(get_current_user_emp_id),
    db: Session = Depends(get_db),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Reject leave request (L1 or L2)"""
    try:
        result = leave_service.reject_leave_request(req_id, current_emp_id, remarks)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/cancel/{req_id}")
def cancel_leave_request(
    req_id: int,
    reason: str = Body(..., embed=True),
    current_emp_id: int = Depends(get_current_user_emp_id),
    db: Session = Depends(get_db),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """Employee cancels their own leave request"""
    try:
        result = leave_service.cancel_leave_request(req_id, current_emp_id, reason)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/admin/all-requests")
def admin_get_all_leave_requests(
    status: Optional[str] = Query(None, description="Filter by status: Pending, Approved, Rejected, Cancelled"),
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    leave_type: Optional[str] = Query(None, description="Filter by leave type"),
    from_date: Optional[str] = Query(None, description="Filter requests from date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter requests to date (YYYY-MM-DD)"),
    limit: Optional[int] = Query(100, description="Limit number of results"),
    offset: Optional[int] = Query(0, description="Offset for pagination"),
    admin_emp_id: int = Depends(validate_admin_access),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to view all leave requests with filtering options
    """
    try:
        query = db.query(LeaveRequest).join(Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id)
        
        # Apply filters
        if status:
            query = query.filter(LeaveRequest.leave_req_status == status)
        
        if employee_id:
            query = query.filter(LeaveRequest.leave_req_emp_id == employee_id)
        
        if leave_type:
            query = query.filter(LeaveRequest.leave_req_type == leave_type)
        
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
                query = query.filter(LeaveRequest.leave_req_from_dt >= from_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
        
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, '%Y-%m-%d').date()
                query = query.filter(LeaveRequest.leave_req_to_dt <= to_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        requests = query.order_by(LeaveRequest.leave_req_id.desc())\
                       .offset(offset)\
                       .limit(limit)\
                       .all()
        
        # Format results
        results = []
        for req in requests:
            employee = req.employee if hasattr(req, 'employee') else db.query(Employee).filter(Employee.emp_id == req.leave_req_emp_id).first()
            
            # Get L1 and L2 manager names
            l1_manager = db.query(Employee).filter(Employee.emp_id == req.leave_req_l1_id).first() if req.leave_req_l1_id else None
            l2_manager = db.query(Employee).filter(Employee.emp_id == req.leave_req_l2_id).first() if req.leave_req_l2_id else None
            
            results.append({
                "request_id": req.leave_req_id,
                "employee": {
                    "emp_id": employee.emp_id,
                    "emp_name": employee.emp_name,
                    "emp_code": employee.emp_code
                } if employee else None,
                "leave_type": req.leave_req_type,
                "from_date": req.leave_req_from_dt.isoformat(),
                "to_date": req.leave_req_to_dt.isoformat(),
                "total_days": float((req.leave_req_to_dt - req.leave_req_from_dt).days + 1),
                "reason": req.leave_req_reason,
                "status": req.leave_req_status,
                "l1_manager": {
                    "emp_id": l1_manager.emp_id,
                    "emp_name": l1_manager.emp_name
                } if l1_manager else None,
                "l1_status": req.leave_req_l1_status,
                "l1_remarks": req.leave_req_l1_remarks,
                "l2_manager": {
                    "emp_id": l2_manager.emp_id,
                    "emp_name": l2_manager.emp_name
                } if l2_manager else None,
                "l2_status": req.leave_req_l2_status,
                "l2_remarks": req.leave_req_l2_remarks,
                "created_at": req.leave_req_id,  # Using ID as creation timestamp placeholder
                "has_attachments": len(req.attachments) > 0 if hasattr(req, 'attachments') else False
            })
        
        return {
            "total_count": total_count,
            "current_page": (offset // limit) + 1 if limit > 0 else 1,
            "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
            "results": results
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving leave requests: {str(e)}")

@router.get("/admin/balance-summary")
def admin_get_balance_summary(
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    admin_emp_id: int = Depends(validate_admin_access),
    db: Session = Depends(get_db),
    leave_service: LeaveService = Depends(get_leave_service)
):
    """
    Admin endpoint to view balance summary for all employees or specific employee
    """
    try:
        if employee_id:
            # Get balance for specific employee
            employee = db.query(Employee).filter(Employee.emp_id == employee_id).first()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            leave_types = db.query(LeaveBalance.lt_leave_type)\
                .filter(LeaveBalance.lt_emp_id == employee_id)\
                .distinct().all()
            
            balances = {}
            for (lt,) in leave_types:
                balances[lt] = leave_service.get_balance_snapshot(employee_id, lt)
            
            return {
                "employee": {
                    "emp_id": employee.emp_id,
                    "emp_name": employee.emp_name,
                    "emp_code": employee.emp_code
                },
                "balances": balances
            }
        else:
            # Get balance summary for all employees
            employees = db.query(Employee).filter(Employee.emp_status == 'Active').all()
            results = []
            
            for employee in employees:
                leave_types = db.query(LeaveBalance.lt_leave_type)\
                    .filter(LeaveBalance.lt_emp_id == employee.emp_id)\
                    .distinct().all()
                
                balances = {}
                for (lt,) in leave_types:
                    balances[lt] = leave_service.get_balance_snapshot(employee.emp_id, lt)
                
                results.append({
                    "employee": {
                        "emp_id": employee.emp_id,
                        "emp_name": employee.emp_name,
                        "emp_code": employee.emp_code
                    },
                    "balances": balances
                })
            
            return {
                "total_employees": len(results),
                "results": results
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving balance summary: {str(e)}")

def resolve_attachment_path(rel_path: str) -> Path:
    """
    Convert a POSIX-style rel path from DB (e.g. 'leave/28/file.png')
    to an absolute filesystem path under UPLOAD_ROOT.
    Also handles any legacy backslashes gracefully.
    """
    parts = rel_path.replace("\\", "/").split("/")
    full = (Path(UPLOAD_ROOT) / Path(*parts)).resolve()
    return full
