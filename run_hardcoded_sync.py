"""Manual runner for hardcoded SAP sync test.

Usage (PowerShell):
  python run_hardcoded_sync.py               # uses today's UTC date
  python run_hardcoded_sync.py 2025-10-04    # specific date

This script constructs the required services similarly to app startup and
invokes the hardcoded sync, printing a JSON summary.
"""
import sys
import asyncio
import json
from datetime import datetime

from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.clock_repo import ClockRepository
from app.services.attendance_service import AttendanceService
from app.services.employee_service import EmployeeService
from app.services.sap_sync_service import SAPSyncService
from app.services.sap_sync_hardcoded import run_test_sync
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
        summary = await run_test_sync(sap_service, date_str)
        print(json.dumps(summary, indent=2))
    finally:
        try:
            db.close()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
