from typing import List, Optional, Tuple
from datetime import date, time, datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import AttendanceRequest, Employee

class AttendanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_with_employee_info(self) -> List[Tuple[AttendanceRequest, str, str, str]]:
        """Get all attendance requests with employee information"""
        try:
            return self.db.query(
                AttendanceRequest,
                Employee.emp_name,
                Employee.emp_department,
                Employee.emp_designation
            ).join(Employee, AttendanceRequest.art_emp_id == Employee.emp_id).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching attendance requests: {str(e)}")

    def get_by_employee_id(self, emp_id: int) -> List[Tuple[AttendanceRequest, Employee]]:
        """Get attendance requests for specific employee"""
        try:
            print(f"[DEBUG] Repo - querying for emp_id: {emp_id}")
            result = self.db.query(AttendanceRequest, Employee).join(
                Employee, AttendanceRequest.art_emp_id == Employee.emp_id
            ).filter(AttendanceRequest.art_emp_id == emp_id).order_by(
                AttendanceRequest.art_date.desc()
            ).all()
            print(f"[DEBUG] Repo - query result: {result}")
            print(f"[DEBUG] Repo - result count: {len(result)}")
            return result
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching employee attendance requests: {str(e)}")

    def get_for_admin(self, admin_emp_id: int) -> List[Tuple[AttendanceRequest, Employee]]:
        """Get attendance requests for admin (L1 only workflow)"""
        try:
            # L1 requests only - L2 workflow disabled for attendance regularization
            l1_reqs = self.db.query(AttendanceRequest, Employee).join(
                Employee, AttendanceRequest.art_emp_id == Employee.emp_id
            ).filter(
                AttendanceRequest.art_l1_id == admin_emp_id,
                AttendanceRequest.art_l1_status.in_(["Approved", "Pending"])
            ).order_by(AttendanceRequest.art_date.desc()).all()

            # L2 workflow commented for future use
            # L2 requests (only approved by L1)
            # l2_reqs = self.db.query(AttendanceRequest, Employee).join(
            #     Employee, AttendanceRequest.art_emp_id == Employee.emp_id
            # ).filter(
            #     AttendanceRequest.art_l2_id == admin_emp_id,
            #     AttendanceRequest.art_l1_status == "Approved"
            # ).order_by(AttendanceRequest.art_date.desc()).all()

            # Return only L1 requests
            return l1_reqs

            # Previous L1+L2 logic commented for future use
            # Combine and deduplicate
            # all_reqs = {req[0].art_id: req for req in l1_reqs + l2_reqs}
            # return sorted(all_reqs.values(), key=lambda x: x[0].art_date, reverse=True)

        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching admin attendance requests: {str(e)}")

    def create(self, emp_id: int, request_date: date, clock_in: time, 
              clock_out: time, reason: str, shift: str, l1_id: int, l2_id: Optional[int]) -> AttendanceRequest:
        """Create a new attendance regularization request"""
        try:
            # Normalize shift to abbreviation expected by FK (emp_shift_tbl.est_shift_abbrv)
            # "General" (full name) should map to "GEN". Accept either already-abbreviated value.
            normalized_shift = shift
            if shift:
                # Exact match for General (case-insensitive)
                if shift.lower() == "general":
                    normalized_shift = "GEN"
                # If shift is provided as full phrase containing General (e.g. "General Shift")
                elif "general" in shift.lower() and len(shift) > 6:
                    normalized_shift = "GEN"
            # Future mappings can be added here (e.g. "Shift I" -> "S1")
            attendance_req = AttendanceRequest(
                art_emp_id=emp_id,
                art_date=request_date,
                art_clockin_time=clock_in,
                art_clockout_time=clock_out,
                art_reason=reason,
                art_status="Pending",
                art_l1_status="Pending",
                # L2 status set to "Not Required" for L1-only workflow
                art_l2_status="Not Required" if l2_id is None else "Pending",
                art_l1_id=l1_id,
                art_l2_id=l2_id,  # This will be None for L1-only workflow
                art_shift=normalized_shift,
                art_applied_date=datetime.utcnow()
            )
            
            self.db.add(attendance_req)
            self.db.commit()
            self.db.refresh(attendance_req)
            return attendance_req
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while creating attendance request: {str(e)}")

    def get_by_id(self, request_id: int) -> Optional[AttendanceRequest]:
        """Get attendance request by ID"""
        try:
            return self.db.query(AttendanceRequest).filter(AttendanceRequest.art_id == request_id).first()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching attendance request: {str(e)}")

    def update_status(self, request_id: int, status: str, l1_status: Optional[str] = None, 
                     l2_status: Optional[str] = None) -> Optional[AttendanceRequest]:
        """Update attendance request status"""
        try:
            req = self.get_by_id(request_id)
            if not req:
                return None

            req.art_status = status
            if l1_status:
                req.art_l1_status = l1_status
            if l2_status:
                req.art_l2_status = l2_status

            self.db.commit()
            self.db.refresh(req)
            return req
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while updating attendance request status: {str(e)}")

    def delete_by_id(self, request_id: int) -> bool:
        """Delete attendance request by ID"""
        try:
            deleted = self.db.query(AttendanceRequest).filter(AttendanceRequest.art_id == request_id).delete()
            self.db.commit()
            return deleted > 0
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while deleting attendance request: {str(e)}")