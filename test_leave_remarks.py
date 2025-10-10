#!/usr/bin/env python3
"""Test script to check leave request remarks in database"""

from app.database import get_db
from app.models import LeaveRequest
from sqlalchemy import text

def test_leave_remarks():
    db = next(get_db())
    
    print("=== Checking LeaveRequest table remarks ===")
    
    try:
        # Check if table exists and has data
        count_query = db.execute(text("SELECT COUNT(*) FROM leave_request_tbl")).scalar()
        print(f"Total records in leave_request_tbl: {count_query}")
        
        # Get some sample data including remarks
        sample_query = db.execute(text("SELECT leave_req_id, leave_req_emp_id, leave_req_reason, remarks FROM leave_request_tbl LIMIT 5")).fetchall()
        print(f"Sample records: {sample_query}")
        
        # Check specifically for leave request ID 36 (from the user's query)
        specific_query = db.execute(text("SELECT leave_req_id, leave_req_emp_id, leave_req_reason, remarks FROM leave_request_tbl WHERE leave_req_id = 36")).fetchone()
        print(f"Leave request 36 details: {specific_query}")
        
        # Check if the remarks column exists
        columns_query = db.execute(text("PRAGMA table_info(leave_request_tbl)")).fetchall()
        print(f"Table structure: {columns_query}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    db.close()

if __name__ == "__main__":
    test_leave_remarks()