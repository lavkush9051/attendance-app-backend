"""
Manual runner for leave sync for a given date.

Usage (PowerShell):
  python run_leave_sync.py               # uses today's UTC date
  python run_leave_sync.py 2025-11-13    # specific date
"""
import sys
import asyncio
from datetime import datetime

from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.clock_repo import ClockRepository
from app.services.attendance_service import AttendanceService
from app.services.employee_service import EmployeeService
from app.services.sap_sync_service import SAPSyncService

from app.database import SessionLocal


def build_services():
    db = SessionLocal()
    employee_repo = EmployeeRepository(db)
    attendance_repo = AttendanceRepository(db)
    clock_repo = ClockRepository(db)
    attendance_service = AttendanceService(attendance_repo, employee_repo, clock_repo)
    employee_service = EmployeeService(employee_repo)
    sap_sync_service = SAPSyncService(attendance_service, employee_service)
    return db, sap_sync_service


async def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    db, sap_service = build_services()
    try:
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        summary = await sap_service.sync_leaves_for_date(target_dt)
        print(summary)
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
