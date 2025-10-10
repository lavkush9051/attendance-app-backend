from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.face_repo import FaceRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.leave_repo import LeaveRepository
from app.repositories.leave_balance_repo import LeaveBalanceRepository
from app.repositories.clock_repo import ClockRepository
from app.services.face_service import FaceService
from app.services.attendance_service import AttendanceService
from app.services.leave_service import LeaveService
from app.services.clock_service import ClockService

def get_face_repo(db: Session = Depends(get_db)) -> FaceRepository:
    return FaceRepository(db)

def get_employee_repo(db: Session = Depends(get_db)) -> EmployeeRepository:
    return EmployeeRepository(db)

def get_attendance_repo(db: Session = Depends(get_db)) -> AttendanceRepository:
    return AttendanceRepository(db)

def get_leave_repo(db: Session = Depends(get_db)) -> LeaveRepository:
    return LeaveRepository(db)

def get_leave_balance_repo(db: Session = Depends(get_db)) -> LeaveBalanceRepository:
    return LeaveBalanceRepository(db)

def get_clock_repo(db: Session = Depends(get_db)) -> ClockRepository:
    return ClockRepository(db)

def get_face_service(
    face_repo: FaceRepository = Depends(get_face_repo),
    employee_repo: EmployeeRepository = Depends(get_employee_repo)
) -> FaceService:
    return FaceService(face_repo, employee_repo)

def get_attendance_service(
    attendance_repo: AttendanceRepository = Depends(get_attendance_repo),
    employee_repo: EmployeeRepository = Depends(get_employee_repo)
) -> AttendanceService:
    return AttendanceService(attendance_repo, employee_repo)

def get_leave_service(
    leave_repo: LeaveRepository = Depends(get_leave_repo),
    leave_balance_repo: LeaveBalanceRepository = Depends(get_leave_balance_repo),
    employee_repo: EmployeeRepository = Depends(get_employee_repo)
) -> LeaveService:
    return LeaveService(leave_repo, leave_balance_repo, employee_repo)

def get_clock_service(
    clock_repo: ClockRepository = Depends(get_clock_repo),
    employee_repo: EmployeeRepository = Depends(get_employee_repo),
    face_service: FaceService = Depends(get_face_service)
) -> ClockService:
    return ClockService(clock_repo, employee_repo, face_service)