from typing import List, Optional, Dict, Any
from datetime import date, datetime, time, timedelta
from app.repositories.clock_repo import ClockRepository
from app.repositories.face_repo import FaceRepository
from app.schemas.clock import (
    ClockInRequest, ClockOutRequest, ClockInResponse, 
    ClockOutResponse, AttendanceRecordResponse
)

class ClockService:
    def __init__(self, clock_repo: ClockRepository, face_repo: FaceRepository):
        self.clock_repo = clock_repo
        self.face_repo = face_repo

    def process_clock_in(self, request: ClockInRequest) -> ClockInResponse:
        """Process employee clock-in with face validation and geofencing"""
        try:
            # Validate shift exists
            shift_info = self.clock_repo.get_shift_by_abbrev(request.shift)
            if not shift_info:
                raise Exception(f"Invalid shift: {request.shift}")

            # Validate face if provided
            if request.face_image:
                face_exists = self.face_repo.exists_for_employee(request.emp_id)
                if not face_exists:
                    raise Exception("No face record found for employee. Please register face first.")
                
                # TODO: Implement actual face recognition comparison
                # For now, we assume face validation passes

            # Check geofencing if coordinates provided
            if request.latitude and request.longitude:
                # TODO: Implement geofencing validation
                # For now, we assume location is valid
                pass

            # Allow multiple clock-ins - repository will handle keeping first clock-in time
            today = datetime.now().date()

            # Create or get existing clock-in record
            clock_record = self.clock_repo.create_clockin(
                emp_id=request.emp_id,
                today=today,
                clockin_time=request.clockin_time or datetime.now().time(),
                shift=request.shift
            )

            return ClockInResponse(
                success=True,
                message="Clock-in successful" if clock_record.cct_clockin_time == (request.clockin_time or datetime.now().time()) else "Clock-in recorded (keeping first time of day)",
                clockin_id=clock_record.cct_id,
                clockin_time=clock_record.cct_clockin_time,
                employee_id=clock_record.cct_emp_id,
                shift=clock_record.cct_shift_abbrv or "Unknown"
            )

        except Exception as e:
            return ClockInResponse(
                success=False,
                message=f"Clock-in failed: {str(e)}",
                clockin_id=None,
                clockin_time=None,
                employee_id=request.emp_id,
                shift=request.shift
            )

    def process_clock_out(self, request: ClockOutRequest) -> ClockOutResponse:
        """Process employee clock-out"""
        try:
            # Find today's clock-in record
            today = datetime.now().date()
            clockin_record = self.clock_repo.get_today_clockin(request.emp_id, today)
            if not clockin_record:
                raise Exception("No clock-in record found for today")

            # Allow multiple clock-outs - always update to latest time

            # Update with clock-out time
            updated_record = self.clock_repo.update_clockout(
                emp_id=request.emp_id,
                today=today,
                clockout_time=request.clockout_time or datetime.now().time()
            )

            if not updated_record:
                raise Exception("Failed to update clock-out record")

            # Calculate worked hours
            worked_hours = self._calculate_worked_hours(
                updated_record.cct_clockin_time, 
                updated_record.cct_clockout_time
            )

            return ClockOutResponse(
                success=True,
                message="Clock-out successful (updated to latest time)",
                clockin_id=updated_record.cct_id,
                clockin_time=updated_record.cct_clockin_time,
                clockout_time=updated_record.cct_clockout_time,
                worked_hours=worked_hours,
                employee_id=updated_record.cct_emp_id
            )

        except Exception as e:
            return ClockOutResponse(
                success=False,
                message=f"Clock-out failed: {str(e)}",
                clockin_id=None,
                clockin_time=None,
                clockout_time=None,
                worked_hours=0.0,
                employee_id=request.emp_id
            )

    def get_employee_attendance_records(self, emp_id: int, 
                                      start_date: Optional[date] = None,
                                      end_date: Optional[date] = None) -> List[AttendanceRecordResponse]:
        """Get attendance records for an employee"""
        try:
            records = self.clock_repo.get_attendance_records(
                emp_id=emp_id,
                start_date=start_date,
                end_date=end_date
            )

            return [
                AttendanceRecordResponse(
                    clockin_id=record.cct_id,
                    employee_id=record.cct_emp_id,
                    date=record.cct_date,
                    clockin_time=record.cct_clockin_time,
                    clockout_time=record.cct_clockout_time,
                    worked_hours=self._calculate_worked_hours(record.cct_clockin_time, record.cct_clockout_time) if record.cct_clockout_time else 0.0,
                    shift=record.cct_shift_abbrv or "Unknown",
                    status="Complete" if record.cct_clockout_time else "Incomplete"
                ) for record in records
            ]

        except Exception as e:
            raise Exception(f"Service error while fetching attendance records: {str(e)}")

    def get_today_status(self, emp_id: int) -> Dict[str, Any]:
        """Get today's attendance status for an employee"""
        try:
            today = datetime.now().date()
            today_record = self.clock_repo.get_today_clockin(emp_id, today)
            
            if not today_record:
                return {
                    'status': 'not_clocked_in',
                    'message': 'No clock-in record for today',
                    'clockin_time': None,
                    'clockout_time': None,
                    'worked_hours': 0.0
                }

            worked_hours = 0.0
            status = 'clocked_in'
            message = 'Clocked in, waiting for clock-out'

            if today_record.cct_clockout_time:
                worked_hours = self._calculate_worked_hours(
                    today_record.cct_clockin_time, 
                    today_record.cct_clockout_time
                )
                status = 'completed'
                message = 'Day completed'

            return {
                'status': status,
                'message': message,
                'clockin_time': today_record.cct_clockin_time,
                'clockout_time': today_record.cct_clockout_time,
                'worked_hours': worked_hours,
                'shift': today_record.cct_shift_abbrv or "Unknown"
            }

        except Exception as e:
            raise Exception(f"Service error while fetching today's status: {str(e)}")

    def get_attendance_summary(self, emp_id: int, month: int, year: int) -> Dict[str, Any]:
        """Get monthly attendance summary for an employee"""
        try:
            # Get records for the month
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)

            records = self.clock_repo.get_attendance_records(
                emp_id=emp_id,
                start_date=start_date,
                end_date=end_date
            )

            total_days = len(records)
            complete_days = len([r for r in records if r.cct_clockout_time])
            incomplete_days = total_days - complete_days

            total_hours = sum([
                self._calculate_worked_hours(r.cct_clockin_time, r.cct_clockout_time) 
                for r in records if r.cct_clockout_time
            ])

            avg_hours = total_hours / complete_days if complete_days > 0 else 0.0

            return {
                'employee_id': emp_id,
                'month': month,
                'year': year,
                'total_attendance_days': total_days,
                'complete_days': complete_days,
                'incomplete_days': incomplete_days,
                'total_worked_hours': round(total_hours, 2),
                'average_daily_hours': round(avg_hours, 2)
            }

        except Exception as e:
            raise Exception(f"Service error while generating attendance summary: {str(e)}")

    def _calculate_worked_hours(self, clockin_time: time, clockout_time: Optional[time]) -> float:
        """Calculate worked hours between clock-in and clock-out"""
        if not clockout_time:
            return 0.0

        # Convert times to datetime for calculation
        today = date.today()
        clockin_dt = datetime.combine(today, clockin_time)
        clockout_dt = datetime.combine(today, clockout_time)

        # Handle overnight shifts
        if clockout_dt < clockin_dt:
            clockout_dt = datetime.combine(today, clockout_time) + timedelta(days=1)

        # Calculate hours
        duration = clockout_dt - clockin_dt
        hours = duration.total_seconds() / 3600

        return round(hours, 2)
