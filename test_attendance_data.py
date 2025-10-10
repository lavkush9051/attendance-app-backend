#!/usr/bin/env python3
"""Test script to check attendance regularization data in database"""

from app.database import get_db
from app.models import AttendanceRequest, Employee
from sqlalchemy import text

def test_attendance_data():
    db = next(get_db())
    
    print("=== Checking AttendanceRequest table ===")
    
    # Check if table exists and has data
    try:
        count_query = db.execute(text("SELECT COUNT(*) FROM attendance_regularization_tbl")).scalar()
        print(f"Total records in attendance_regularization_tbl: {count_query}")
        
        # Get some sample data
        sample_query = db.execute(text("SELECT art_id, art_emp_id, art_date, art_reason, art_status FROM attendance_regularization_tbl LIMIT 5")).fetchall()
        print(f"Sample records: {sample_query}")
        
        # Check specifically for employee 10001
        emp_query = db.execute(text("SELECT art_id, art_emp_id, art_date, art_reason, art_status FROM attendance_regularization_tbl WHERE art_emp_id = 10001")).fetchall()
        print(f"Records for employee 10001: {emp_query}")
        
        # Check if employee 10001 exists
        emp_exists = db.execute(text("SELECT emp_id, emp_name FROM employee_tbl WHERE emp_id = 10001")).fetchone()
        print(f"Employee 10001 exists: {emp_exists}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    db.close()

if __name__ == "__main__":
    test_attendance_data()