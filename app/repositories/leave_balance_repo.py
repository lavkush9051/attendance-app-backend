from typing import List, Optional, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, and_, extract, text
from app.models import LeaveBalance, LeaveRequest, LeaveLedger

# Map leave type names to LeaveBalance column names
# LEAVE_COL_MAP = {
#     "Casual Leave": "lt_casual_leave",
#     "Earned Leave": "lt_earned_leave", 
#     "Half Pay Leave": "lt_half_pay_leave",
#     "Medical Leave": "lt_medical_leave",
#     "Compensatory Off": "lt_compensatory_off",
#     "Optional Holiday": "lt_optional_holiday",
#     # "Special Leave": "lt_special_leave",
#     # "Child Care Leave": "lt_child_care_leave",
#     # "Parental Leave": "lt_parental_leave",
# }
LEAVE_COL_MAP = {
    "Casual Leave": "lt_casual_leave",
    "Earned Leave": "lt_earned_leave",
    "Half Pay Leave": "lt_half_pay_leave",
    "Medical Leave": "lt_medical_leave",
    "Optional Holiday": "lt_optional_holiday",
    "Compensatory off": "lt_compensatory_off",
    "Commuted Leave": "lt_commuted_leave",
}

class LeaveBalanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_employee_id(self, emp_id: int) -> Optional[LeaveBalance]:
        """Get leave balance record for an employee"""
        try:
            return self.db.query(LeaveBalance).filter(
                LeaveBalance.lt_emp_id == emp_id
            ).first()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching employee leave balances: {str(e)}")

    def get_by_employee_and_type(self, emp_id: int, leave_type: str) -> Optional[float]:
        """Get specific leave balance for employee and leave type"""
        try:
            balance_record = self.get_by_employee_id(emp_id)
            if not balance_record:
                return None
            key = (leave_type or "").strip() # changes to lower case for matching
            column_name = LEAVE_COL_MAP.get(key) # passes key to get correct column name
            if not column_name:
                raise Exception(f"Unknown leave type: {leave_type} (normalized='{key}')")
            
           # Safe getattr: if attribute missing, return 0
            val = getattr(balance_record, column_name, 0)
            # ensure numeric
            return float(val or 0)
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching leave balance: {str(e)}")

    def get_available_balance(self, emp_id: int, leave_type: str, year: int = None) -> float:
        """Calculate available leave balance from allocated minus used (from LeaveLedger)"""
        try:
            # Get allocated balance from LeaveBalance table
            allocated = self.get_by_employee_and_type(emp_id, leave_type)
            if allocated is None:
                return 0.0
            # Normalize leave type
            normalized = (leave_type or "").strip()
            # Calculate used days from LeaveLedger with COMMIT status
            used_days = self.db.query(func.coalesce(func.sum(LeaveLedger.ll_qty), 0)).filter(
            LeaveLedger.ll_emp_id == emp_id,
            LeaveLedger.ll_leave_type == normalized,
            LeaveLedger.ll_action == "COMMIT"
        ).scalar() or 0

            return float(allocated) - float(used_days)

        except SQLAlchemyError as e:
            raise Exception(f"Database error while calculating available balance: {str(e)}")

    def check_sufficient_balance(self, emp_id: int, leave_type: str, 
                                required_days: float, year: int = None) -> bool:
        """Check if employee has sufficient leave balance"""
        try:
            available = self.get_available_balance(emp_id, leave_type, year)
            return available >= required_days
        except Exception as e:
            raise Exception(f"Error checking leave balance sufficiency: {str(e)}")

    def update_used_days(self, emp_id: int, leave_type: str, 
                        days_to_add: float, year: int = None) -> bool:
        """Update used days - for this model, this is handled via LeaveRequest records"""
        try:
            # In this model structure, used days are calculated from LeaveRequest records
            # So this method doesn't need to update the LeaveBalance table directly
            # Just return True to indicate success
            return True
        except Exception as e:
            raise Exception(f"Error updating used days: {str(e)}")

    def get_employee_summary(self, emp_id: int, year: int = None) -> Dict[str, Any]:
        """Get complete leave balance summary for an employee"""
        try:
            if year is None:
                year = date.today().year

            balance_record = self.get_by_employee_id(emp_id)
            if not balance_record:
                return {
                    'employee_id': emp_id,
                    'year': year,
                    'balances': {},
                    'total_allocated': 0.0,
                    'total_used': 0.0,
                    'total_available': 0.0
                }

            # Calculate used days from LeaveLedger with COMMIT status
            used_from_ledger = self.db.query(
                LeaveLedger.ll_leave_type,
                func.sum(LeaveLedger.ll_qty).label('total_used')
            ).filter(
                LeaveLedger.ll_emp_id == emp_id,
                LeaveLedger.ll_action == "COMMIT",
                extract('year', LeaveLedger.ll_created_at) == year
            ).group_by(LeaveLedger.ll_leave_type).all()

            used_dict = {item.ll_leave_type: float(item.total_used or 0) for item in used_from_ledger}

            summary = {
                'employee_id': emp_id,
                'year': year,
                'balances': {},
                'total_allocated': 0.0,
                'total_used': 0.0,
                'total_available': 0.0
            }

            # Process each leave type
            for leave_type, column_name in LEAVE_COL_MAP.items():
                allocated = getattr(balance_record, column_name, 0)
                used = used_dict.get(leave_type, 0.0)
                available = allocated - used

                summary['balances'][leave_type] = {
                    'allocated': allocated,
                    'used': used,
                    'available': available
                }

                summary['total_allocated'] += allocated
                summary['total_used'] += used
                summary['total_available'] += available

            return summary

        except SQLAlchemyError as e:
            raise Exception(f"Database error while generating employee summary: {str(e)}")