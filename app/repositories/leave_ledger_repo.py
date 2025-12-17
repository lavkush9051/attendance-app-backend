from typing import List, Optional, Dict, Any
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, and_
from app.models import LeaveLedger

class LeaveLedgerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_hold(self, emp_id: int, leave_type: str, qty: float, ref_leave_req_id: int) -> LeaveLedger:
        """Create a HOLD entry in the leave ledger"""
        try:
            hold_entry = LeaveLedger(
                ll_emp_id=emp_id,
                ll_leave_type=leave_type,
                ll_qty=qty,
                ll_action="HOLD",
                ll_ref_leave_req_id=ref_leave_req_id
            )
            self.db.add(hold_entry)
            self.db.flush()  # Get ID without committing
            return hold_entry
        except SQLAlchemyError as e:
            raise Exception(f"Database error while creating HOLD ledger entry: {str(e)}")

    def create_release(self, emp_id: int, leave_type: str, qty: float, ref_leave_req_id: int) -> Optional[LeaveLedger]:
        """Create a RELEASE entry in the leave ledger (with idempotency check)"""
        try:
            # Check outstanding hold amount for this request
            # outstanding = self.get_total_by_action_and_request(ref_leave_req_id, "HOLD")
            # already_released = self.get_total_by_action_and_request(ref_leave_req_id, "RELEASE")
            
            # if outstanding <= already_released:
            #     return None  # Nothing to release (idempotent)
            
            # Idempotency: if already released for this request, skip
            existing = self.db.query(LeaveLedger).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id,
                LeaveLedger.ll_action == "RELEASE"
            ).first()
            
            if existing:
                return None  # Already released (idempotent)
            
            # COMMIT to RELEASE
            existing_commit = self.db.query(LeaveLedger).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id,
                LeaveLedger.ll_action == "COMMIT"
            ).first()

            if existing_commit:
                existing_commit.ll_action = "RELEASE"

                self.db.add(existing_commit)
                self.db.flush()

                return existing_commit
            
            # HOLD to RELEASE (if cancel by user before commit)
            existing_hold = self.db.query(LeaveLedger).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id,
                LeaveLedger.ll_action == "HOLD"
            ).first()
            if existing_hold:
                existing_hold.ll_action = "RELEASE"

                self.db.add(existing_hold)
                self.db.flush()

                return existing_hold
            
            release_entry = LeaveLedger(
                ll_emp_id=emp_id,
                ll_leave_type=leave_type,
                ll_qty=qty,
                ll_action="RELEASE",
                ll_ref_leave_req_id=ref_leave_req_id
            )
            self.db.add(release_entry)
            self.db.flush()  # Get ID without committing
            return release_entry
        except SQLAlchemyError as e:
            raise Exception(f"Database error while creating RELEASE ledger entry: {str(e)}")

    def create_commit(self, emp_id: int, leave_type: str, qty: float, ref_leave_req_id: int) -> Optional[LeaveLedger]:
        """Create a COMMIT entry in the leave ledger (with idempotency check)"""
        try:
            # Idempotency: if already committed for this request, skip
            existing = self.db.query(LeaveLedger).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id,
                LeaveLedger.ll_action == "COMMIT"
            ).first()
            
            if existing:
                return None  # Already committed (idempotent)
            
            existing_hold = self.db.query(LeaveLedger).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id,
                LeaveLedger.ll_action == "HOLD"
            ).first()

            if existing_hold:
                existing_hold.ll_action = "COMMIT"

                self.db.add(existing_hold)
                self.db.flush()

                return existing_hold
            
            
            commit_entry = LeaveLedger(
                ll_emp_id=emp_id,
                ll_leave_type=leave_type,
                ll_qty=qty,
                ll_action="COMMIT",
                ll_ref_leave_req_id=ref_leave_req_id
            )
            self.db.add(commit_entry)
            self.db.flush()  # Get ID without committing
            return commit_entry
        except SQLAlchemyError as e:
            raise Exception(f"Database error while creating COMMIT ledger entry: {str(e)}")

    def get_total_by_action_and_request(self, ref_leave_req_id: int, action: str) -> float:
        """Get total quantity for a specific action and leave request"""
        try:
            total = self.db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0)).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id,
                LeaveLedger.ll_action == action
            ).scalar()
            return float(total or 0.0)
        except SQLAlchemyError as e:
            raise Exception(f"Database error while calculating ledger totals: {str(e)}")

    def get_balance_totals(self, emp_id: int, leave_type: str) -> Dict[str, float]:
        """Get balance totals for employee and leave type (held, committed)"""
        try:
            # Calculate held amount: sum(HOLD) - sum(RELEASE)
            held_total = self.db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0)).filter(
                LeaveLedger.ll_emp_id == emp_id,
                LeaveLedger.ll_leave_type == leave_type,
                LeaveLedger.ll_action == "HOLD"
            ).scalar()
            
            released_total = self.db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0)).filter(
                LeaveLedger.ll_emp_id == emp_id,
                LeaveLedger.ll_leave_type == leave_type,
                LeaveLedger.ll_action == "RELEASE"
            ).scalar()
            
            held = max(0.0, float(held_total or 0.0) - float(released_total or 0.0))
            
            # Calculate committed amount: sum(COMMIT)
            committed_total = self.db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0.0)).filter(
                LeaveLedger.ll_emp_id == emp_id,
                LeaveLedger.ll_leave_type == leave_type,
                LeaveLedger.ll_action == "COMMIT"
            ).scalar()
            print(f"[DEBUG] Leave_type:{leave_type}, Committed total from DB: {committed_total},released_total: {released_total}, held_total: {held_total}")
            committed = float(committed_total or 0.0)
            
            return {
                "held": held,
                "committed": committed
            }
        except SQLAlchemyError as e:
            raise Exception(f"Database error while calculating balance totals: {str(e)}")

    def get_ledger_entries_by_request(self, ref_leave_req_id: int) -> List[LeaveLedger]:
        """Get all ledger entries for a specific leave request"""
        try:
            return self.db.query(LeaveLedger).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id
            ).order_by(LeaveLedger.ll_id.asc()).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching ledger entries: {str(e)}")

    def get_employee_ledger_history(self, emp_id: int, leave_type: Optional[str] = None, 
                                   from_date: Optional[date] = None, to_date: Optional[date] = None) -> List[LeaveLedger]:
        """Get ledger history for an employee with optional filters"""
        try:
            query = self.db.query(LeaveLedger).filter(LeaveLedger.ll_emp_id == emp_id)
            
            if leave_type:
                query = query.filter(LeaveLedger.ll_leave_type == leave_type)
            
            if from_date:
                query = query.filter(LeaveLedger.ll_created_at >= from_date)
            
            if to_date:
                query = query.filter(LeaveLedger.ll_created_at <= to_date)
            
            return query.order_by(LeaveLedger.ll_created_at.desc()).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching employee ledger history: {str(e)}")

    def get_audit_trail(self, ref_leave_req_id: int) -> List[Dict[str, Any]]:
        """Get complete audit trail for a leave request"""
        try:
            entries = self.get_ledger_entries_by_request(ref_leave_req_id)
            
            audit_trail = []
            for entry in entries:
                audit_trail.append({
                    "id": entry.ll_id,
                    "employee_id": entry.ll_emp_id,
                    "leave_type": entry.ll_leave_type,
                    "quantity": entry.ll_qty,
                    "action": entry.ll_action,
                    "timestamp": entry.ll_created_at,
                    "reference_request_id": entry.ll_ref_leave_req_id
                })
            
            return audit_trail
        except Exception as e:
            raise Exception(f"Error generating audit trail: {str(e)}")

    def delete_by_request_id(self, ref_leave_req_id: int) -> int:
        """Delete all ledger entries for a specific leave request (for cleanup)"""
        try:
            deleted_count = self.db.query(LeaveLedger).filter(
                LeaveLedger.ll_ref_leave_req_id == ref_leave_req_id
            ).delete()
            return deleted_count
        except SQLAlchemyError as e:
            raise Exception(f"Database error while deleting ledger entries: {str(e)}")

    def verify_ledger_integrity(self, ref_leave_req_id: int) -> Dict[str, Any]:
        """Verify ledger integrity for a leave request"""
        try:
            entries = self.get_ledger_entries_by_request(ref_leave_req_id)
            
            totals = {"HOLD": 0.0, "RELEASE": 0.0, "COMMIT": 0.0}
            for entry in entries:
                totals[entry.ll_action] += entry.ll_qty
            
            # Calculate net amounts
            net_held = totals["HOLD"] - totals["RELEASE"]
            net_committed = totals["COMMIT"]
            
            # Check integrity rules
            integrity_issues = []
            
            # Rule 1: Net held should be >= 0
            if net_held < 0:
                integrity_issues.append("Negative net held amount (more released than held)")
            
            # Rule 2: For committed requests, net held should be 0 (all held amount should be committed or released)
            if net_committed > 0 and net_held != 0:
                integrity_issues.append("Committed request has non-zero net held amount")
            
            return {
                "request_id": ref_leave_req_id,
                "totals": totals,
                "net_held": net_held,
                "net_committed": net_committed,
                "has_integrity_issues": len(integrity_issues) > 0,
                "integrity_issues": integrity_issues
            }
        except Exception as e:
            raise Exception(f"Error verifying ledger integrity: {str(e)}")