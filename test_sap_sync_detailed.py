import asyncio
import logging
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.clock_repo import ClockRepository
from app.services.attendance_service import AttendanceService
from app.services.employee_service import EmployeeService
from app.services.sap_sync_service import SAPSyncService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_sap_sync():
    # Create DB session
    db = SessionLocal()
    
    try:
        # Initialize repositories and services
        employee_repo = EmployeeRepository(db)
        attendance_repo = AttendanceRepository(db)
        clock_repo = ClockRepository(db)
        
        attendance_service = AttendanceService(attendance_repo, employee_repo, clock_repo)
        employee_service = EmployeeService(employee_repo)
        
        # Initialize SAP sync service
        sap_sync_service = SAPSyncService(attendance_service, employee_service)
        
        # Define shifts mapping between ID and abbreviation
        shifts = [
            {"id": 1, "name": "Shift I", "abbrev": "I"},
            {"id": 2, "name": "Shift II", "abbrev": "II"},
            {"id": 3, "name": "Shift III", "abbrev": "III"},
            {"id": 4, "name": "General", "abbrev": "GEN"}
        ]
        
        # Test syncing for all shifts
        current_date = datetime(2025, 11, 17)  # put hardcoded date
        logger.info(f"Testing SAP sync for date: {current_date.date()}")
        
        for shift in shifts:
            logger.info(f"\nProcessing {shift['name']} ({shift['abbrev']})...")
            
            # Get employees in this shift
            employees = await employee_service.get_employees_by_shift(shift['id'])
            logger.info(f"Found {len(employees) if employees else 0} employees in {shift['name']}")
            
            if employees:
                for emp in employees:
                    logger.info(f"Checking attendance for employee {emp.get('emp_id')} ({emp.get('emp_name', 'Unknown')})")
                    attendance = await attendance_service.get_employee_attendance(
                        emp['emp_id'], 
                        current_date.date()
                    )
                    if attendance:
                        logger.info(f"Found attendance record: Clock in: {attendance.get('clock_in')}, Clock out: {attendance.get('clock_out')}")
                    else:
                        logger.info("No attendance record found")
            
            # Try to sync the shift
            await sap_sync_service.sync_shift_attendance(shift['id'], current_date)
            logger.info(f"Completed sync attempt for {shift['name']}")
            if hasattr(sap_sync_service, '_sync_error') and sap_sync_service._sync_error:
                logger.error(f"Aborting all further shift syncs for the day due to SAP error in {shift['name']}.")
                break
        logger.info("\nAll SAP sync tests completed")
        
    except Exception as e:
        logger.error(f"Error during SAP sync test: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_sap_sync())