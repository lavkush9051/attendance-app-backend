from typing import List, Optional, Tuple, Dict, Any
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, and_, func
from app.models import LeaveRequest, Employee

class LeaveRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_with_employee_info(self) -> List[Tuple[LeaveRequest, str, str, str]]:
        """Get all leave requests with employee information"""
        try:
            return self.db.query(
                LeaveRequest,
                Employee.emp_name,
                Employee.emp_department,
                Employee.emp_designation
            ).join(Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching leave requests: {str(e)}")

    def get_by_employee_id(self, emp_id: int) -> List[Tuple[LeaveRequest, Employee]]:
        """Get leave requests for specific employee"""
        try:
            return self.db.query(LeaveRequest, Employee).join(
                Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id
            ).filter(LeaveRequest.leave_req_emp_id == emp_id).order_by(
                LeaveRequest.leave_req_from_dt.desc()
            ).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching employee leave requests: {str(e)}")

    def get_for_admin(self, admin_emp_id: int) -> List[Tuple[LeaveRequest, Employee]]:
        """Get leave requests for admin approval (L1 and L2) with visibility rules"""
        try:
            # L1 requests - L1 can see all requests assigned to them (including rejected ones)
            l1_reqs = self.db.query(LeaveRequest, Employee).join(
                Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id
            ).filter(
                LeaveRequest.leave_req_l1_id == admin_emp_id
            ).order_by(LeaveRequest.leave_req_from_dt.desc()).all()

            # L2 requests with visibility rules
            l2_reqs = self.db.query(LeaveRequest, Employee).join(
                Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id
            ).filter(
                LeaveRequest.leave_req_l2_id == admin_emp_id,
                # L2 can see:
                # 1. Requests approved by L1 (for normal workflow)
                # 2. Requests rejected by L2 themselves (for review)
                # BUT NOT requests rejected by L1
                or_(
                    LeaveRequest.leave_req_l1_status == "Approved",
                    LeaveRequest.leave_req_l2_status == "Rejected"
                )
            ).order_by(LeaveRequest.leave_req_from_dt.desc()).all()

            # Combine and deduplicate
            all_reqs = {req[0].leave_req_id: req for req in l1_reqs + l2_reqs}
            return sorted(all_reqs.values(), key=lambda x: x[0].leave_req_from_dt, reverse=True)

        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching admin leave requests: {str(e)}")

    def create(self, emp_id: int, from_date: date, to_date: date, 
              leave_type: str, reason: str, l1_id: int, l2_id: int, 
              total_days: float, immediate_reporting_officer: str) -> LeaveRequest:
        """Create a new leave request"""
        try:
            leave_req = LeaveRequest(
                leave_req_emp_id=emp_id,
                leave_req_from_dt=from_date,
                leave_req_to_dt=to_date,
                leave_req_type=leave_type,
                leave_req_reason=reason,
                leave_req_status="Pending",  # Initial status matching old system
                leave_req_l1_status="Pending",
                leave_req_l2_status="Pending",
                leave_req_l1_id=immediate_reporting_officer,
                leave_req_l2_id= None,
                leave_req_applied_dt=date.today(),
            )
            print(f"[DEBUG] Creating leave request: {leave_req}")
            self.db.add(leave_req)
            self.db.commit()
            self.db.refresh(leave_req)
            return leave_req
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while creating leave request: {str(e)}")

    def get_by_id(self, request_id: int) -> Optional[LeaveRequest]:
        """Get leave request by ID"""
        try:
            return self.db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == request_id).first()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching leave request: {str(e)}")

    def update_status(self, request_id: int, status: str, l1_status: Optional[str] = None, 
                     l2_status: Optional[str] = None, next_reporting_officer: str=None) -> Optional[LeaveRequest]:
        """Update leave request status"""
        try:
            req = self.get_by_id(request_id)
            if not req:
                return None

            req.leave_req_status = status
            #req.leave_req_l2_id = next_reporting_officer
            if next_reporting_officer:
                req.leave_req_l2_id = next_reporting_officer
            if l1_status:
                req.leave_req_l1_status = l1_status
            if l2_status:
                req.leave_req_l2_status = l2_status

            self.db.commit()
            self.db.refresh(req)
            return req
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while updating leave request status: {str(e)}")

    def update_ledger_status(self, request_id: int, ledger_status: str) -> Optional[LeaveRequest]:
        """Update leave request ledger status (HOLD/RELEASE/COMMIT)"""
        try:
            req = self.get_by_id(request_id)
            if not req:
                return None

            req.leave_req_status = ledger_status
            self.db.commit()
            self.db.refresh(req)
            return req
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while updating leave ledger status: {str(e)}")

    def get_overlapping_leaves(self, emp_id: int, from_date: date, to_date: date, 
                              exclude_id: Optional[int] = None) -> List[LeaveRequest]:
        """Get overlapping leave requests for an employee"""
        try:
            query = self.db.query(LeaveRequest).filter(
                LeaveRequest.leave_req_emp_id == emp_id,
                or_(
                    and_(LeaveRequest.leave_req_from_dt <= from_date, LeaveRequest.leave_req_to_dt >= from_date),
                    and_(LeaveRequest.leave_req_from_dt <= to_date, LeaveRequest.leave_req_to_dt >= to_date),
                    and_(LeaveRequest.leave_req_from_dt >= from_date, LeaveRequest.leave_req_to_dt <= to_date)
                ),
                LeaveRequest.leave_req_status != "Rejected" and LeaveRequest.leave_req_status != "Cancelled"
            )
            
            if exclude_id:
                query = query.filter(LeaveRequest.leave_req_id != exclude_id)
            
            return query.all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while checking overlapping leaves: {str(e)}")

    def get_leave_summary(self, emp_id: int, year: Optional[int] = None) -> Dict[str, Any]:
        """Get leave summary for an employee"""
        try:
            query = self.db.query(
                LeaveRequest.leave_req_type,
                func.sum(
                    func.extract('day', LeaveRequest.leave_req_to_dt - LeaveRequest.leave_req_from_dt) + 1
                ).label('total_days'),
                func.count(LeaveRequest.leave_req_id).label('total_requests')
            ).filter(
                LeaveRequest.leave_req_emp_id == emp_id,
                LeaveRequest.leave_req_status.in_(["COMMIT", "Approved"])
            )
            
            if year:
                query = query.filter(func.extract('year', LeaveRequest.leave_req_from_dt) == year)
            
            results = query.group_by(LeaveRequest.leave_req_type).all()
            
            summary = {
                'leave_types': {},
                'total_days_taken': 0,
                'total_requests': 0
            }
            
            for result in results:
                summary['leave_types'][result.leave_req_type] = {
                    'days': float(result.total_days or 0),
                    'requests': result.total_requests
                }
                summary['total_days_taken'] += float(result.total_days or 0)
                summary['total_requests'] += result.total_requests
            
            return summary
        except SQLAlchemyError as e:
            raise Exception(f"Database error while generating leave summary: {str(e)}")

    def delete_by_id(self, request_id: int) -> bool:
        """Delete leave request by ID"""
        try:
            deleted = self.db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == request_id).delete()
            self.db.commit()
            return deleted > 0
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while deleting leave request: {str(e)}")

    def get_pending_leaves(self, emp_id: Optional[int] = None) -> List[LeaveRequest]:
        """Get pending leave requests (optionally filtered by employee)"""
        try:
            query = self.db.query(LeaveRequest).filter(
                or_(
                    LeaveRequest.leave_req_l1_status == "Pending",
                    and_(
                        LeaveRequest.leave_req_l1_status == "Approved",
                        LeaveRequest.leave_req_l2_status == "Pending"
                    )
                )
            )
            
            if emp_id:
                query = query.filter(LeaveRequest.leave_req_emp_id == emp_id)
            
            return query.order_by(LeaveRequest.leave_req_from_dt.asc()).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching pending leaves: {str(e)}")

    def get_pending_sap_sync(self, target_date: date) -> List[Tuple[LeaveRequest, Employee]]:
        """Get approved leaves starting on target_date that haven't been synced to SAP yet.
        
        Returns leaves where:
        - leave_req_status = 'Approved'
        - leave_req_from_dt = target_date
        - sap_sync_status = 'PENDING'
        """
        try:
            return self.db.query(LeaveRequest, Employee).join(
                Employee, LeaveRequest.leave_req_emp_id == Employee.emp_id
            ).filter(
                LeaveRequest.leave_req_status == "Approved",
                LeaveRequest.leave_req_from_dt == target_date,
                LeaveRequest.sap_sync_status == "PENDING"
            ).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching pending SAP sync leaves: {str(e)}")

    def mark_synced_with_sap(self, leave_req_id: int) -> None:
        """Mark leave request as synced with SAP by updating status to SENT and recording timestamp."""
        try:
            req = self.get_by_id(leave_req_id)
            if req:
                req.sap_sync_status = "SENT"
                req.sap_sync_timestamp = datetime.utcnow()
                self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while marking leave as synced: {str(e)}")