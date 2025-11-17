import asyncio
import logging
from datetime import datetime
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
    try:
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
            
            # Test syncing for all shifts
            # Use a recent date where we know there's attendance data
            current_date = datetime(2023, 11, 3)  # Use November 3rd, 2023
            shifts = [
                {"id": 1, "name": "Morning Shift"},
                {"id": 2, "name": "Afternoon Shift"},
                {"id": 3, "name": "Night Shift"}
            ]
            
            for shift in shifts:
                logger.info(f"Testing SAP sync for {shift['name']} (ID: {shift['id']})...")
                await sap_sync_service.sync_shift_attendance(shift['id'], current_date)
                logger.info(f"Completed sync test for {shift['name']}")
                
            logger.info("All SAP sync tests completed successfully.")
            
        finally:
            db.close()

    except Exception as e:
        print(f"Error during SAP sync test: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_sap_sync())