from typing import Optional, List
from datetime import date, time
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import ClockInClockOut, EmpShift

class ClockRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_today_clockin(self, emp_id: int, today: date) -> Optional[ClockInClockOut]:
        """Get today's clock-in record for employee"""
        try:
            return self.db.query(ClockInClockOut).filter(
                ClockInClockOut.cct_emp_id == emp_id,
                ClockInClockOut.cct_date == today,
                ClockInClockOut.cct_clockin_time != None
            ).first()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching clock-in record: {str(e)}")

    def create_clockin(self, emp_id: int, today: date, clockin_time: time, shift: str) -> ClockInClockOut:
        """Create clock-in record or return existing one (keeps first clock-in time)"""
        try:
            # Check if record already exists for today
            existing_record = self.db.query(ClockInClockOut).filter(
                ClockInClockOut.cct_emp_id == emp_id,
                ClockInClockOut.cct_date == today
            ).first()
            
            if existing_record:
                # Record exists - keep the first clock-in time, don't update
                print(f"[DEBUG] Clock-in record exists for emp {emp_id} on {today}. Keeping first clock-in time: {existing_record.cct_clockin_time}")
                return existing_record
            else:
                # Create new record - this is the first clock-in
                clockin_record = ClockInClockOut(
                    cct_emp_id=emp_id,
                    cct_date=today,
                    cct_clockin_time=clockin_time,
                    cct_shift_abbrv=shift
                )
                self.db.add(clockin_record)
                self.db.commit()
                self.db.refresh(clockin_record)
                print(f"[DEBUG] Created new clock-in record for emp {emp_id} at {clockin_time}")
                return clockin_record
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while creating clock-in record: {str(e)}")

    def update_clockout(self, emp_id: int, today: date, clockout_time: time) -> Optional[ClockInClockOut]:
        """Update clock-out time for today's record (always updates to latest time)"""
        try:
            record = self.db.query(ClockInClockOut).filter(
                ClockInClockOut.cct_emp_id == emp_id,
                ClockInClockOut.cct_date == today
            ).first()
            
            if record:
                # Always update to the latest clock-out time
                print(f"[DEBUG] Updating clock-out for emp {emp_id} from {record.cct_clockout_time} to {clockout_time}")
                record.cct_clockout_time = clockout_time
                self.db.commit()
                self.db.refresh(record)
            else:
                print(f"[ERROR] No clock-in record found for emp {emp_id} on {today}")
            
            return record
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while updating clock-out: {str(e)}")

    def get_shift_by_abbrev(self, shift_abbrev: str) -> Optional[EmpShift]:
        """Get shift details by abbreviation"""
        try:
            return self.db.query(EmpShift).filter(EmpShift.est_shift_abbrv == shift_abbrev).first()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching shift: {str(e)}")

    def get_attendance_records(self, emp_id: int, start_date: date, end_date: date) -> List[ClockInClockOut]:
        """Get attendance records for date range"""
        try:
            return self.db.query(ClockInClockOut).filter(
                ClockInClockOut.cct_emp_id == emp_id,
                ClockInClockOut.cct_date >= start_date,
                ClockInClockOut.cct_date <= end_date
            ).all()
        except SQLAlchemyError as e:
            raise Exception(f"Database error while fetching attendance records: {str(e)}")

    def create_or_update_record(self, emp_id: int, record_date: date, 
                               clockin_time: time, clockout_time: time, shift: str) -> ClockInClockOut:
        """Create new record or update existing one"""
        try:
            existing = self.db.query(ClockInClockOut).filter(
                ClockInClockOut.cct_emp_id == emp_id,
                ClockInClockOut.cct_date == record_date
            ).first()

            if existing:
                existing.cct_clockin_time = clockin_time
                existing.cct_clockout_time = clockout_time
                existing.cct_shift_abbrv = shift
                record = existing
            else:
                record = ClockInClockOut(
                    cct_emp_id=emp_id,
                    cct_date=record_date,
                    cct_clockin_time=clockin_time,
                    cct_clockout_time=clockout_time,
                    cct_shift_abbrv=shift
                )
                self.db.add(record)

            self.db.commit()
            self.db.refresh(record)
            return record
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error while creating/updating clock record: {str(e)}")