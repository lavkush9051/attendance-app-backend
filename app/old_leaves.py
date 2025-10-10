from fastapi import APIRouter, Form, Body, Query, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
import os
from pathlib import Path
from app.database import SessionLocal, get_db
from app.models import LeaveRequest, Employee, LeaveBalance, LeaveType, LeaveLedger, LeaveAttachment
from app.storage import save_upload_to_disk
from app.config import UPLOAD_ROOT
from app.dependencies import get_current_user_emp_id, validate_admin_access
from app.auth import get_current_user

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
}

@router.get("/leave-requests") 
def get_all_leave_requests(
    current_emp_id: int = Depends(get_current_user_emp_id)
):
    """Get leave requests for current user (admin view if admin, employee view otherwise)"""
    session = SessionLocal()
    # Filter: Show requests where admin is L1 or L2 manager
    results = session.query(
        LeaveRequest,
        Employee.emp_name,
        Employee.emp_department,
        Employee.emp_designation
    ).join(Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id
    ).filter(
       (
            (LeaveRequest.leave_req_l1_id == current_emp_id)
        ) | (
            (LeaveRequest.leave_req_l2_id == current_emp_id) &
            (LeaveRequest.leave_req_l1_status == "Approved")
        )
    ).all()
    session.close()

    leave_requests = []
    for lr, emp_name, emp_department, emp_designation in results:
        lr_dict = jsonable_encoder(lr)
        lr_dict["emp_name"] = emp_name
        lr_dict["emp_department"] = emp_department
        lr_dict["emp_designation"] = emp_designation
        leave_requests.append(lr_dict)
    return JSONResponse(content=leave_requests)

@router.get("/leave-requests/{emp_id}")
def get_leave_requests(
    emp_id: int,
    admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Get leave requests for employee or admin view"""
    # If not admin, return as before
    if not admin:
        requests = (
            db.query(LeaveRequest, Employee)
            .join(Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id)
            .filter(LeaveRequest.leave_req_emp_id == emp_id)
            .order_by(LeaveRequest.leave_req_from_dt.desc())
            .all()
        )
    else:
        # ADMIN MODE: emp_id here is the admin's ID!
        # Find all leave requests where this admin is l1 or l2
        l1_reqs = (
            db.query(LeaveRequest, Employee)
            .join(Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id)
            .filter(LeaveRequest.leave_req_l1_id == emp_id)
            .filter(LeaveRequest.leave_req_l1_status.in_(["Approved", "Pending", "Rejected"]))
            .order_by(LeaveRequest.leave_req_from_dt.desc())
            .all()
        )
        l2_reqs = (
            db.query(LeaveRequest, Employee)
            .join(Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id)
            .filter(LeaveRequest.leave_req_l2_id == emp_id)
            .filter(LeaveRequest.leave_req_l1_status == "Approved")  # Only if L1 approved
            .order_by(LeaveRequest.leave_req_from_dt.desc())
            .all()
        )
        # Combine L1 and L2 requests, and remove duplicates (if any)
        requests = list({(lr.leave_req_id, lr, emp) for lr, emp in l1_reqs + l2_reqs})
        # Now unpack tuples
        requests = [(lr, emp) for _, lr, emp in requests]

    print(f"[DEBUG] Found {len(requests)} leave requests for emp_id {emp_id} (admin={admin})")
    result = []
    for lr, emp in requests:
        result.append({
            "id": lr.leave_req_id,
            "emp_id": lr.leave_req_emp_id,
            "employee_name": emp.emp_name,
            "emp_department": emp.emp_department,
            "leave_type_name": lr.leave_req_type,
            "start_date": str(lr.leave_req_from_dt),
            "end_date": str(lr.leave_req_to_dt),
            "reason": lr.leave_req_reason,
            "status": lr.leave_req_status,
            "l1_status": lr.leave_req_l1_status,
            "l2_status": lr.leave_req_l2_status,
            "remarks": lr.remarks or "",
            "applied_date": str(lr.leave_req_applied_dt) if lr.leave_req_applied_dt else "-",
        })
    print(f"[DEBUG] Returning {len(result)} leave requests")
    return result

@router.post("/leave-request")
async def create_leave_request(
    emp_id: int = Form(...),
    leave_type: str = Form(...),
    leave_from_dt: str = Form(...),
    leave_to_dt: str = Form(...),
    leave_reason: str = Form(...),
    leave_applied_dt: str = Form(...),
    files: List[UploadFile] = File(default=[]),
):
    """Create a new leave request"""
    print(f"[DEBUG] Creating leave request for emp_id {emp_id} from {leave_from_dt} to {leave_to_dt}")
    session: Session = SessionLocal()
    try:
        # Lookup L1 and L2 for this employee
        emp = session.query(Employee).filter(Employee.emp_id == emp_id).first()
        if not emp:
            session.close()
            raise HTTPException(status_code=404, detail="Employee not found")

        from_date = datetime.strptime(leave_from_dt, "%Y-%m-%d").date()
        to_date = datetime.strptime(leave_to_dt, "%Y-%m-%d").date()
        leave_applied_dt = datetime.strptime(leave_applied_dt, "%Y-%m-%d").date()

        # Compute quantity (days). Adjust function if you want to include weekends/holidays.
        print(f"[DEBUG] Calculating leave quantity from {from_date} to {to_date}")
        qty = business_days_inclusive(from_date, to_date)
        if qty <= 0:
            session.close()
            raise HTTPException(status_code=400, detail="Invalid date range")

        # Check available balance snapshot
        print(f"[DEBUG] Checking leave balance for emp_id {emp_id}, type {leave_type}")
        snap = get_balance_snapshot(session, emp_id, leave_type)
        if snap["available"] < qty:
            session.close()
            return JSONResponse(
                status_code=400,
                content={
                    "status": "failed",
                    "error": f"Insufficient balance. Available={snap['available']} required={qty}"
                },
            )

        leave_req = LeaveRequest(
            leave_req_emp_id=emp_id,
            leave_req_type=leave_type,
            leave_req_from_dt=from_date,
            leave_req_to_dt=to_date,
            leave_req_reason=leave_reason,
            leave_req_status="Pending",
            leave_req_l1_status="Pending",
            leave_req_l2_status="Pending",
            leave_req_l1_id=emp.emp_l1,
            leave_req_l2_id=emp.emp_l2,
            remarks="",
            leave_req_applied_dt=leave_applied_dt
        )
        
        session.add(leave_req)
        session.flush()  # to get leave_req.leave_req_id
        print(f"[DEBUG] Created leave_req_id {leave_req.leave_req_id}, recording HOLD in ledger")
        ledger_hold(session, emp_id, leave_type, qty, leave_req.leave_req_id)
        session.commit()
        leave_req_id = leave_req.leave_req_id

        # Handle file uploads
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
                la_uploaded_by=emp_id,
            ))
        session.commit()
        session.close()
        return {"status": "success", "leave_req_id": leave_req_id}
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.put("/leave-request/action")
async def leave_action(
    leave_req_id: int = Body(...),
    action: str = Body(...),      # "approve" or "reject"
    admin_id: int = Body(...),
    remarks: str = Body(None)  # New remarks field
):
    """Handle leave request approval/rejection with ledger operations"""
    print(f"[LOG] Leave action by admin {admin_id} on request {leave_req_id} with action {action} and remarks {remarks}")
    session: Session = SessionLocal()
    try:
        req = session.query(LeaveRequest).filter(LeaveRequest.leave_req_id == leave_req_id).first()
        if not req:
            session.close()
            return JSONResponse(status_code=404, content={"error": "Leave request not found"})

        # Compute qty for ledger ops
        qty = business_days_inclusive(req.leave_req_from_dt, req.leave_req_to_dt)
        emp_id = req.leave_req_emp_id
        ltype = req.leave_req_type

        action = action.lower().strip()
        if action not in ("approve", "reject", "cancel"):
            print(f"[ERROR] Invalid action: {action}")
            session.close()
            return JSONResponse(status_code=400, content={"error": "Invalid action"})

        # L1 action
        if getattr(req, "leave_req_l1_id", None) == admin_id:
            if action in ["approve"]:
                req.leave_req_l1_status = "Approved"
                req.leave_req_status = "L1 Approved"
                # HOLD remains in place (no ledger change)
            else:
                # reject: RELEASE hold
                req.leave_req_l1_status = "Rejected"
                req.leave_req_status = "Rejected"
                ledger_release(session, emp_id, ltype, qty, req.leave_req_id)

        # L2 action
        elif getattr(req, "leave_req_l2_id", None) == admin_id:
            if action not in ("approve", "reject"):
                session.close()
                return JSONResponse(status_code=400, content={"error": "Invalid action for L2"})    
            if req.leave_req_l1_status != "Approved":
                session.close()
                return JSONResponse(status_code=403, content={"error": "L1 must approve before L2 can act"})

            if action == "approve":
                req.leave_req_l2_status = "Approved"
                req.leave_req_status = "Approved"
                # Finalize: RELEASE HOLD and COMMIT
                ledger_release(session, emp_id, ltype, qty, req.leave_req_id)
                ledger_commit(session, emp_id, ltype, qty, req.leave_req_id)
            else:
                req.leave_req_l2_status = "Rejected"
                req.leave_req_status = "Rejected"
                # Rejection at L2 → RELEASE hold
                ledger_release(session, emp_id, ltype, qty, req.leave_req_id)

        # User Cancel (Revoke) Action
        elif action == "cancel":
            req.leave_req_status = "Cancelled"
            cancel_remark = remarks.strip() if remarks else "Cancelled by user"
            if req.remarks:
                existing = req.remarks.strip().split("\n")
                if cancel_remark not in existing:
                    req.remarks = req.remarks.strip() + "\n" + cancel_remark
            else:
                req.remarks = cancel_remark

        else:
            session.close()
            return JSONResponse(status_code=403, content={"error": "You are not authorized to act on this request"})

       # Append remark safely
        if action in ["approve", "reject"] and remarks:
            new_remarks = remarks.strip()
            if req.remarks:
                existing = req.remarks.strip().split("\n")
                # Only add if not already present (avoid duplicates)
                if new_remarks not in existing:
                    req.remarks = req.remarks.strip() + "\n" + new_remarks
            else:
                req.remarks = new_remarks
        
        print(f"[DB SAVE] Final remarks stored: {req.remarks}")
        session.add(req)
        updated_remarks = req.remarks  # Capture updated remarks
        session.commit()
        session.close()
        return {"status": "success", "remarks": updated_remarks}

    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={"status": "failed", "error": str(e)})
    finally:
        session.close()

@router.delete("/leave-requests/{leave_req_id}")
def delete_leave_request(leave_req_id: int):
    """Delete a leave request"""
    session: Session = SessionLocal()
    try:
        leave_req = session.query(LeaveRequest).filter(LeaveRequest.leave_req_id == leave_req_id).first()
        if not leave_req:
            session.close()
            raise HTTPException(status_code=404, detail="Leave request not found")
        session.delete(leave_req)
        session.commit()
        session.close()
        return {"status": "success"}
    except Exception as e:
        session.rollback()
        session.close()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leave-balance/snapshot")
def get_leave_balance_snapshot(emp_id: int = Query(...), db: Session = Depends(get_db)):
    """
    Returns per-type balances using the HOLD/RELEASE/COMMIT ledger:
      accrued   -> from leave_tbl
      held      -> sum(HOLD) - sum(RELEASE)
      committed -> sum(COMMIT)
      available -> accrued - committed - max(0, held)
    """
    # 1) load the base accrual row
    lb = db.query(LeaveBalance).filter(LeaveBalance.lt_emp_id == emp_id).one_or_none()
    if not lb:
        # if no row yet, just act as zeros for all types
        base = {k: 0.0 for k in LEAVE_COL_MAP.keys()}
    else:
        base = {}
        for leave_type, col_name in LEAVE_COL_MAP.items():
            base[leave_type] = float(getattr(lb, col_name) or 0)

    # 2) aggregate the ledger per type & action
    rows = (
        db.query(
            LeaveLedger.ll_leave_type.label("type"),
            LeaveLedger.ll_action.label("action"),
            func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0).label("qty"),
        )
        .filter(LeaveLedger.ll_emp_id == emp_id)
        .group_by(LeaveLedger.ll_leave_type, LeaveLedger.ll_action)
        .all()
    )

    ledger = {}
    for r in rows:
        ledger.setdefault(r.type, {}).setdefault(r.action, 0.0)
        ledger[r.type][r.action] += float(r.qty or 0.0)

    # 3) build per-type snapshot
    items = []
    totals = {"accrued": 0.0, "held": 0.0, "committed": 0.0, "available": 0.0}

    for leave_type in LEAVE_COL_MAP.keys():
        accrued = base.get(leave_type, 0.0)
        act = ledger.get(leave_type, {})
        hold = float(act.get("HOLD", 0.0) - act.get("RELEASE", 0.0))
        if hold < 0:
            hold = 0.0  # clamp, should not go negative
        committed = float(act.get("COMMIT", 0.0))
        available = float(accrued - committed - hold)
        if available < 0:
            available = 0.0  # optional clamp

        items.append({
            "type": leave_type,
            "accrued": round(accrued, 2),
            "held": round(hold, 2),
            "committed": round(committed, 2),
            "available": round(available, 2),
        })

        totals["accrued"] += accrued
        totals["held"] += hold
        totals["committed"] += committed
        totals["available"] += available

    # round totals for neatness
    for k in totals:
        totals[k] = round(totals[k], 2)

    return {
        "emp_id": emp_id,
        "types": items,
        "totals": totals,
    }

@router.get("/leave-balance")
def get_leave_balance(emp_id: int = Query(...)):
    """Get basic leave balance for an employee"""
    session: Session = SessionLocal()
    try:
        lb = (
            session.query(LeaveBalance)
            .filter(LeaveBalance.lt_emp_id == emp_id)
            .first()
        )

        if not lb:
            session.close()
            return JSONResponse(
                status_code=404,
                content={"status": "failed", "error": "Leave balance not found for this employee"},
            )

        data = {
            "emp_id": lb.lt_emp_id,
            "casual_leave": lb.lt_casual_leave,
            "earned_leave": lb.lt_earned_leave,
            "half_pay_leave": lb.lt_half_pay_leave,
            "medical_leave": lb.lt_medical_leave,
            "special_leave": lb.lt_special_leave,
            "child_care_leave": lb.lt_child_care_leave,
            "parental_leave": lb.lt_parental_leave,
        }

        session.close()
        return {"status": "success", "data": data}

    except Exception as e:
        session.rollback()
        session.close()
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "error": str(e)},
        )

@router.get("/leave-types")
def get_leave_types(db: Session = Depends(get_db)):
    """Get all available leave types"""
    leave_types = db.query(LeaveType).all()
    # Convert to dict
    result = [
        {
            "type": l.lt_leave_type,
            "abrev": l.lt_abrev,
            "total": l.lt_total
        }
        for l in leave_types
    ]
    return {"leave_types": result}

@router.post("/leave-requests/{leave_req_id}/attachments")
async def upload_attachments(leave_req_id: int, files: List[UploadFile] = File(...), uploader_emp_id: int = Form(...)):
    """Upload attachments for a leave request"""
    session: Session = SessionLocal()
    try:
        # (Optionally, verify uploader is the request owner)
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
    db: Session = Depends(get_db),
):
    """Get metadata for leave request attachments"""
    req = db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == leave_req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if actor_emp_id is not None:
        allowed = { req.leave_req_emp_id, getattr(req, "leave_req_l1_id", None), getattr(req, "leave_req_l2_id", None) }
        if actor_emp_id not in allowed:
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
    db: Session = Depends(get_db),
):
    """Download leave request attachment"""
    print(f"[ATTACHMENT][GET] leave_req_id={leave_req_id}, actor_emp_id={actor_emp_id}")

    req = db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == leave_req_id).first()
    if not req:
        print(f"[ATTACHMENT] leave request not found")
        raise HTTPException(status_code=404, detail="Leave request not found")

    # simple auth: requester, L1, L2
    if actor_emp_id is not None:
        allowed = {
            req.leave_req_emp_id,
            getattr(req, "leave_req_l1_id", None),
            getattr(req, "leave_req_l2_id", None),
        }
        print(f"[ATTACHMENT] allowed={allowed}, actor={actor_emp_id}")
        if actor_emp_id not in allowed:
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

def ledger_hold(db: Session, emp_id: int, leave_type: str, qty: float, req_id: int):
    """Create a HOLD entry in the leave ledger"""
    db.add(LeaveLedger(
        ll_emp_id=emp_id, ll_leave_type=leave_type, ll_qty=qty,
        ll_action="HOLD", ll_ref_leave_req_id=req_id
    ))

def ledger_release(db: Session, emp_id: int, leave_type: str, qty: float, req_id: int):
    """Create a RELEASE entry in the leave ledger"""
    # Guard: release only if there is outstanding hold amount for this request
    outstanding = db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0))\
        .filter(LeaveLedger.ll_emp_id == emp_id,
                LeaveLedger.ll_leave_type == leave_type,
                LeaveLedger.ll_ref_leave_req_id == req_id,
                LeaveLedger.ll_action == "HOLD")\
        .scalar()
    already_released = db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0))\
        .filter(LeaveLedger.ll_emp_id == emp_id,
                LeaveLedger.ll_leave_type == leave_type,
                LeaveLedger.ll_ref_leave_req_id == req_id,
                LeaveLedger.ll_action == "RELEASE")\
        .scalar()
    if float(outstanding or 0) <= float(already_released or 0):
        return  # nothing to release (idempotent)
    db.add(LeaveLedger(
        ll_emp_id=emp_id, ll_leave_type=leave_type, ll_qty=qty,
        ll_action="RELEASE", ll_ref_leave_req_id=req_id
    ))

def ledger_commit(db: Session, emp_id: int, leave_type: str, qty: float, req_id: int):
    """Create a COMMIT entry in the leave ledger"""
    # Idempotency: if already committed for this req, skip
    exists = db.query(LeaveLedger)\
        .filter(LeaveLedger.ll_ref_leave_req_id == req_id,
                LeaveLedger.ll_action == "COMMIT").first()
    if exists:
        return
    db.add(LeaveLedger(
        ll_emp_id=emp_id, ll_leave_type=leave_type, ll_qty=qty,
        ll_action="COMMIT", ll_ref_leave_req_id=req_id
    ))

def resolve_attachment_path(rel_path: str) -> Path:
    """
    Convert a POSIX-style rel path from DB (e.g. 'leave/28/file.png')
    to an absolute filesystem path under UPLOAD_ROOT.
    Also handles any legacy backslashes gracefully.
    """
    parts = rel_path.replace("\\", "/").split("/")
    full = (Path(UPLOAD_ROOT) / Path(*parts)).resolve()
    return full
