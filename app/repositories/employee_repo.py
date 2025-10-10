from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import Employee
from app.schemas.employees import EmployeeResponse

class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[Employee]:
        """Get all employees"""
        try:
            return self.db.query(Employee).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching employees: {str(e)}")

    def get_by_id(self, emp_id: int) -> Optional[Employee]:
        """Get employee by ID"""
        try:
            return self.db.query(Employee).filter(Employee.emp_id == emp_id).first()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching employee {emp_id}: {str(e)}")

    def get_by_ids(self, emp_ids: List[int]) -> List[Employee]:
        """Get employees by IDs"""
        try:
            return self.db.query(Employee).filter(Employee.emp_id.in_(emp_ids)).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching employees by IDs: {str(e)}")

    def update_weekoff(self, emp_ids: List[int], weekoff: str) -> int:
        """Update weekoff for multiple employees"""
        try:
            updated = self.db.query(Employee).filter(Employee.emp_id.in_(emp_ids)).update(
                {Employee.emp_weekoff: weekoff}, synchronize_session=False
            )
            self.db.commit()
            return updated
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while updating weekoff: {str(e)}")

    def exists(self, emp_id: int) -> bool:
        """Check if employee exists"""
        try:
            return self.db.query(Employee.emp_id).filter(Employee.emp_id == emp_id).first() is not None
        except SQLAlchemyError as e:
            raise Exception(f"Database error while checking employee existence: {str(e)}")

    def get_reporting_hierarchy(self, emp_id: int) -> dict:
        """Get reporting hierarchy for an employee (returns L1 and L2 manager IDs)"""
        try:
            employee = self.get_by_id(emp_id)
            if not employee:
                return {'l1_id': None, 'l2_id': None}
            
            return {
                'l1_id': employee.emp_l1,
                'l2_id': employee.emp_l2
            }
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching reporting hierarchy: {str(e)}")