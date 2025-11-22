#!/usr/bin/env python3
"""Test script to insert clock in/out test data"""

from app.database import get_db
from app.models import ClockInClockOut, Employee, EmpShift
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def insert_test_data():
    db = next(get_db())
    try:
        # First make sure we have test employees
        employees = [
            Employee(
                emp_id=10001,
                emp_name="Test Employee 1",
                emp_designation="Software Developer",
                emp_department="IT"
            ),
            Employee(
                emp_id=10002,
                emp_name="Test Employee 2",
                emp_designation="System Admin",
                emp_department="IT"
            )
        ]
        
        # Create test shifts if they don't exist
        shifts = [
            EmpShift(
                est_shift_id=1,
                est_shift_name="Morning Shift",
                est_shift_abbrv="MS",

                est_shift_start_time=datetime.strptime("07:30", "%H:%M").time(),
                est_shift_end_time=datetime.strptime("15:30", "%H:%M").time()
            ),
            EmpShift(
                est_shift_id=2,
                est_shift_name="Afternoon Shift",
                est_shift_abbrv="AS",

                est_shift_start_time=datetime.strptime("15:30", "%H:%M").time(),
                est_shift_end_time=datetime.strptime("23:30", "%H:%M").time()
            ),
            EmpShift(
                est_shift_id=3,
                est_shift_name="Night Shift",
                est_shift_abbrv="NS",

                est_shift_start_time=datetime.strptime("23:30", "%H:%M").time(),
                est_shift_end_time=datetime.strptime("07:30", "%H:%M").time()
            )
        ]
        
        # Add test clock data for today and previous days
        today = datetime.now().date()
        test_date = today - timedelta(days=1)  # Use yesterday's date
        
        clock_data = [
            # Morning Shift test data
            ClockInClockOut(
                cct_emp_id=10001,
                cct_date=test_date,
                cct_clockin_time=datetime.strptime("08:00", "%H:%M").time(),
                cct_clockout_time=datetime.strptime("16:00", "%H:%M").time(),
                cct_shift_abbrv="MS"
            ),
            # Afternoon Shift test data
            ClockInClockOut(
                cct_emp_id=10002,
                cct_date=test_date,
                cct_clockin_time=datetime.strptime("16:00", "%H:%M").time(),
                cct_clockout_time=datetime.strptime("23:00", "%H:%M").time(),
                cct_shift_abbrv="AS"
            ),
            # Night Shift test data
            ClockInClockOut(
                cct_emp_id=10001,
                cct_date=test_date - timedelta(days=1),  # Use day before yesterday for night shift
                cct_clockin_time=datetime.strptime("23:30", "%H:%M").time(),
                cct_clockout_time=datetime.strptime("07:00", "%H:%M").time(),
                cct_shift_abbrv="NS"
            )
        ]
        
        # Insert test employees
        for emp in employees:
            existing = db.query(Employee).filter(Employee.emp_id == emp.emp_id).first()
            if not existing:
                db.add(emp)
                logger.info(f"Added test employee: {emp.emp_name}")
        
        # Insert test shifts
        for shift in shifts:
            existing = db.query(EmpShift).filter(EmpShift.est_shift_id == shift.est_shift_id).first()
            if not existing:
                db.add(shift)
                logger.info(f"Added test shift: {shift.est_shift_name}")
        
        # Commit shifts first to avoid foreign key issues
        db.commit()
        
        # Insert clock data
        for clock in clock_data:
            existing = db.query(ClockInClockOut).filter(
                ClockInClockOut.cct_emp_id == clock.cct_emp_id,
                ClockInClockOut.cct_date == clock.cct_date
            ).first()
            if not existing:
                db.add(clock)
                logger.info(f"Added clock data for employee {clock.cct_emp_id} on {clock.cct_date}")
        
        db.commit()
        logger.info("Test data inserted successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error inserting test data: {str(e)}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    insert_test_data()