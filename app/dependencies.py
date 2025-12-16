from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Union, Optional
from app.database import get_db
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.clock_repo import ClockRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.leave_repo import LeaveRepository
from app.repositories.leave_balance_repo import LeaveBalanceRepository
from app.repositories.leave_ledger_repo import LeaveLedgerRepository
from app.repositories.face_repo import FaceRepository
from app.services.employee_service import EmployeeService
from app.services.clock_service import ClockService
from app.services.attendance_service import AttendanceService
from app.services.leave_service import LeaveService
from app.services.face_service import FaceService

# Repository Dependencies
def get_employee_repository(db: Session = Depends(get_db)) -> EmployeeRepository:
    """Get employee repository instance"""
    return EmployeeRepository(db)

def get_clock_repository(db: Session = Depends(get_db)) -> ClockRepository:
    """Get clock repository instance"""
    return ClockRepository(db)

def get_attendance_repository(db: Session = Depends(get_db)) -> AttendanceRepository:
    """Get attendance repository instance"""
    return AttendanceRepository(db)

def get_leave_repository(db: Session = Depends(get_db)) -> LeaveRepository:
    """Get leave repository instance"""
    return LeaveRepository(db)

def get_leave_balance_repository(db: Session = Depends(get_db)) -> LeaveBalanceRepository:
    """Get leave balance repository instance"""
    return LeaveBalanceRepository(db)

def get_face_repository(db: Session = Depends(get_db)) -> FaceRepository:
    """Get face repository instance"""
    return FaceRepository(db)

def get_leave_ledger_repository(db: Session = Depends(get_db)) -> LeaveLedgerRepository:
    """Get leave ledger repository instance"""
    return LeaveLedgerRepository(db)

# Service Dependencies
def get_employee_service(
    employee_repo: EmployeeRepository = Depends(get_employee_repository)
) -> EmployeeService:
    """Get employee service instance"""
    return EmployeeService(employee_repo)

def get_clock_service(
    clock_repo: ClockRepository = Depends(get_clock_repository),
    face_repo: FaceRepository = Depends(get_face_repository)
) -> ClockService:
    """Get clock service instance"""
    return ClockService(clock_repo, face_repo)

def get_attendance_service(
    attendance_repo: AttendanceRepository = Depends(get_attendance_repository),
    employee_repo: EmployeeRepository = Depends(get_employee_repository),
    clock_repo: ClockRepository = Depends(get_clock_repository)
) -> AttendanceService:
    """Get attendance service instance"""
    return AttendanceService(attendance_repo, employee_repo, clock_repo)

def get_leave_service(
    leave_repo: LeaveRepository = Depends(get_leave_repository),
    leave_balance_repo: LeaveBalanceRepository = Depends(get_leave_balance_repository),
    employee_repo: EmployeeRepository = Depends(get_employee_repository),
    leave_ledger_repo: LeaveLedgerRepository = Depends(get_leave_ledger_repository),
    clock_repo: ClockRepository = Depends(get_clock_repository),
    db: Session = Depends(get_db)
) -> LeaveService:
    """Get leave service instance"""
    return LeaveService(leave_repo, leave_balance_repo, employee_repo, leave_ledger_repo, clock_repo, db)

def get_face_service(
    face_repo: FaceRepository = Depends(get_face_repository)
) -> FaceService:
    """Get face service instance"""
    return FaceService(face_repo)

# Authentication Dependencies
from app.auth import get_current_user, get_current_employee_id as get_current_user_emp_id
from typing import Dict, Any

def get_current_user_info() -> Dict[str, Any]:
    """Get current authenticated user information"""
    return Depends(get_current_user)

def validate_admin_access(current_emp_id: int = Depends(get_current_user_emp_id)) -> int:
    """Validate admin access - checks if user has admin privileges"""
    from app.models import Employee
    
    db = next(get_db())
    try:
        employee = db.query(Employee).filter(Employee.emp_id == current_emp_id).first()
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Check if employee has admin privileges (L1 or L2 manager)
        # This is a simple check - you can enhance based on your business rules
        if not (employee.emp_designation and 
                any(role in employee.emp_designation.lower() 
                    for role in ['manager', 'lead', 'head', 'director', 'admin'])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges for admin access"
            )
        
        return current_emp_id
    finally:
        db.close()

def get_optional_current_user() -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, None otherwise (for optional auth routes)"""
    from app.auth import security, decode_token
    
    def optional_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict[str, Any]]:
        if not credentials:
            return None
        
        try:
            payload = decode_token(credentials.credentials)
            if payload and payload.get("username"):
                return {"username": payload["username"], "payload": payload}
        except:
            pass
        
        return None
    
    return Depends(optional_auth)