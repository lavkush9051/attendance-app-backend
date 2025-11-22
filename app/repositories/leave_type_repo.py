from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import LeaveType

class LeaveTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_sap_leave_id(self, leave_type_name: str) -> Optional[int]:
        """Get SAP leave ID for a given leave type name.
        
        Args:
            leave_type_name: The leave type name (e.g., 'Medical Leave', 'Casual Leave')
        
        Returns:
            SAP leave ID (Absence_type) or None if not found
        """
        try:
            leave_type = self.db.query(LeaveType).filter(
                LeaveType.lt_leave_type == leave_type_name
            ).first()
            return leave_type.sap_leave_id if leave_type else None
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching SAP leave ID: {str(e)}")

    def get_all(self):
        """Get all leave types"""
        try:
            return self.db.query(LeaveType).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching leave types: {str(e)}")
