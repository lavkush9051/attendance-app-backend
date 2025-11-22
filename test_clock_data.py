#!/usr/bin/env python3
"""Test script to check clock in/out data in database"""

from app.database import get_db
from sqlalchemy import text
from datetime import datetime, timedelta

def test_clock_data():
    db = next(get_db())
    
    print("=== Checking ClockInClockOut table ===")
    
    try:
        # Check total records
        count_query = db.execute(text("SELECT COUNT(*) FROM clock_in_clock_out_tbl")).scalar()
        print(f"Total records in clock_in_clock_out_tbl: {count_query}")
        
        # Get records from the last 7 days
        today = datetime.now()
        last_week = today - timedelta(days=7)
        
        recent_query = text("""
            SELECT 
                cct_emp_id, 
                cct_date, 
                cct_clock_in, 
                cct_clock_out, 
                cct_shift_abbrv 
            FROM clock_in_clock_out_tbl 
            WHERE cct_date >= :last_week
            ORDER BY cct_date DESC, cct_emp_id
        """)
        
        recent_records = db.execute(recent_query, {"last_week": last_week}).fetchall()
        print("\nRecent records from the last 7 days:")
        for record in recent_records:
            print(record)
        
        # Get records for employee 10001
        emp_query = text("""
            SELECT 
                cct_emp_id, 
                cct_date, 
                cct_clock_in, 
                cct_clock_out, 
                cct_shift_abbrv 
            FROM clock_in_clock_out_tbl 
            WHERE cct_emp_id = 10001
            ORDER BY cct_date DESC
            LIMIT 5
        """)
        
        emp_records = db.execute(emp_query).fetchall()
        print("\nRecent records for employee 10001:")
        for record in emp_records:
            print(record)
        
    except Exception as e:
        print(f"Error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    test_clock_data()