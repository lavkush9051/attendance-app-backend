import asyncio
import aiohttp
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
from app.core.config import settings
from app.services.attendance_service import AttendanceService
from app.services.employee_service import EmployeeService

logger = logging.getLogger(__name__)

class SAPSyncService:
    """SAPSyncService handles collecting attendance rows and sending them to external systems.

    Note: a separate helper runner `app.services.sap_sync_hardcoded` is available to
    trigger a one-time hardcoded sync for testing."""

    async def get_employees_by_shift_and_date(self, shift_id: int, target_date: str) -> list:
        """
        Fetch employees from clockinclockout table for a given date and shift,
        joining with employee_tbl on emp_id and cct_emp_id.
        Only returns records NOT yet synced (cct_synced_with_sap != 'Y').
        Returns a list of dicts with relevant attendance and employee info.
        """
        from app.database import SessionLocal
        from app.models import ClockInClockOut, Employee
        results = []
        db = SessionLocal()
        try:
            # Query clockinclockout records joined with employee
            query = (
                db.query(
                    ClockInClockOut.cct_emp_id,
                    ClockInClockOut.cct_clockin_time,
                    ClockInClockOut.cct_clockout_time,
                    Employee.emp_id,
                    Employee.emp_name,
                    ClockInClockOut.cct_shift_abbrv
                )
                .join(Employee, Employee.emp_id == ClockInClockOut.cct_emp_id)
                .filter(
                    ClockInClockOut.cct_shift_abbrv == self._get_shift_abbrev(shift_id),
                    ClockInClockOut.cct_date == target_date,
                    ClockInClockOut.cct_synced_with_sap != 'Y'
                )
            )
            
            for row in query.all():
                results.append({
                    "emp_id": row.emp_id,
                    "emp_code": str(row.emp_id),  # Use emp_id as emp_code
                    "shift_id": shift_id,
                    "clock_in": row.cct_clockin_time,
                    "clock_out": row.cct_clockout_time,
                    "clockin_date": target_date
                })
        finally:
            db.close()
        return results
    
    def _get_shift_abbrev(self, shift_id: int) -> str:
        """Map shift ID to abbreviation"""
        shift_map = {1: "I", 2: "II", 3: "III", 4: "GEN"}
        return shift_map.get(shift_id, "I")
    def __init__(self, attendance_service: AttendanceService, employee_service: EmployeeService):
        self.attendance_service = attendance_service
        self.employee_service = employee_service
        self.sap_attendance_url = settings.SAP_BASE_URL + settings.SAP_ATTENDANCE_PATH + "/punch"
        self.sap_leave_url = settings.SAP_BASE_URL + settings.SAP_LEAVE_PATH + "/leave"
        self.sap_auth = (settings.SAP_USERNAME, settings.SAP_PASSWORD)
        # Track which employees have already been sent per date to avoid duplicates across shifts
        # key: date string 'YYYY-MM-DD' -> set of emp_ids
        self._sent_by_date = {}
        
    async def _send_to_sap(self, payload: Dict[str, Any]) -> bool:
        """Send a single attendance record to SAP."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.sap_attendance_url}?sap-client={settings.SAP_CLIENT}",
                    json=payload,
                    auth=aiohttp.BasicAuth(self.sap_auth[0], self.sap_auth[1]),
                    headers={"Content-Type": "application/json", "Accept": "application/json"}
                ) as response:
                    status = response.status
                    # Read text first (safe) then try json if needed
                    body_text = await response.text()
                    if status == 200:
                        # SAP sometimes returns empty or non-JSON bodies; accept 200 as success
                        try:
                            # attempt to parse JSON for richer logging
                            response_data = None
                            if body_text:
                                response_data = await response.json()
                            if response_data is not None:
                                logger.info(f"SAP sync success for emp {payload.get('emp_code')}: {response_data}")
                            else:
                                logger.info(f"SAP sync success for emp {payload.get('emp_code')}: non-JSON or empty response: {body_text}")
                        except Exception:
                            # JSON parsing failed but status is 200 — still consider success
                            logger.info(f"SAP sync success for emp {payload.get('emp_code')}: non-JSON response: {body_text}")
                        return True
                    else:
                        logger.error(f"SAP sync failed for emp {payload.get('emp_code')} status={status}: {body_text}")
                        return False
        except Exception as e:
            # Network or parse errors
            try:
                emp_code = payload.get('emp_code')
            except Exception:
                emp_code = None
            logger.error(f"Error sending to SAP for emp {emp_code}: {str(e)}")
            return False

    def _calculate_hours(self, clock_in: str, clock_out: str) -> str:
        """Calculate hours worked in decimal format."""
        try:
            in_time = datetime.strptime(clock_in, "%H:%M")
            out_time = datetime.strptime(clock_out, "%H:%M")
            # Handle overnight shifts: if out_time <= in_time, assume next day
            if out_time <= in_time:
                out_time = out_time + timedelta(days=1)
            diff = out_time - in_time
            hours = diff.total_seconds() / 3600
            return f"{hours:.2f}"
        except Exception as e:
            logger.error(f"Error calculating hours: {str(e)}")
            return "0.00"

    def _to_sap_date(self, yyyymmdd: str) -> str:
        """Convert 'YYYY-MM-DD' to 'DD.MM.YYYY' for SAP."""
        try:
            parts = str(yyyymmdd).split("-")
            if len(parts) == 3:
                return f"{parts[2]}.{parts[1]}.{parts[0]}"
        except Exception:
            pass
        return yyyymmdd

    def _to_sap_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust payload for SAP: drop emp_id and format dates as DD.MM.YYYY."""
        out = {k: v for k, v in payload.items() if k != "emp_id"}
        if "clockin_date" in out:
            out["clockin_date"] = self._to_sap_date(out["clockin_date"]) if out["clockin_date"] else out["clockin_date"]
        if "clockout_date" in out:
            out["clockout_date"] = self._to_sap_date(out["clockout_date"]) if out["clockout_date"] else out["clockout_date"]
        return out

    async def send_attendance_payload(self, payload: Dict[str, Any]) -> bool:
        """Send attendance payload using settings toggle: 'sap' or 'node'."""
        target = getattr(settings, "SAP_SEND_VIA", "node").lower()
        if target == "sap":
            sap_payload = self._to_sap_payload(payload)
            logger.info(f"SAP payload after transformation: {sap_payload}")
            return await self._send_to_sap(sap_payload)
        ##default to node server
        return await self._send_to_node_server(payload)

    async def sync_shift_attendance(self, shift_id: int, current_date: datetime) -> None:
        """Sync one shift's attendance for a specific date, one-by-one, stop on first error.

        Uses clockinclockout data via get_employees_by_shift_and_date.
        Maintains an in-memory sent set per date and marks DB records as synced upon success.
        """
        self._sync_error = False  # Reset error flag at start of each shift
        try:
            # Prepare date handling
            date_key = current_date.strftime("%Y-%m-%d") if hasattr(current_date, 'strftime') else str(current_date)
            if hasattr(current_date, 'date'):
                date_obj = current_date.date()
            else:
                try:
                    from datetime import datetime as _dt
                    date_obj = _dt.strptime(str(current_date), "%Y-%m-%d").date()
                except Exception:
                    date_obj = None

            # Keep track of employees we've already sent for this sync_date to avoid duplicates across shifts
            sent_emp_ids = self._sent_by_date.setdefault(date_key, set())

            # Fetch rows for this shift and date from clockinclockout
            rows = await self.get_employees_by_shift_and_date(shift_id, date_key)
            logger.info(f"Found {len(rows)} clock rows for shift {shift_id} on {date_key}")

            # Process rows sequentially (queue-like behavior) and stop on first error
            for row in rows:
                try:
                    emp_id_int = int(row.get("emp_id")) if row.get("emp_id") is not None else None
                except Exception:
                    emp_id_int = None

                if emp_id_int in sent_emp_ids:
                    logger.info(f"Skipping duplicate send for employee {emp_id_int} (already sent for {date_key})")
                    continue

                # Format times safely
                def _fmt_time(v):
                    if v is None:
                        return None
                    try:
                        return v.strftime("%H:%M") if hasattr(v, 'strftime') else str(v)
                    except Exception:
                        return str(v)

                clock_in = _fmt_time(row.get("clock_in"))
                clock_out = _fmt_time(row.get("clock_out"))

                if not clock_in or not clock_out:
                    logger.info(f"No complete attendance record found for employee {row.get('emp_id')} on {date_key}")
                    continue

                payload = {
                    "emp_code": str(row.get("emp_code") or row.get("emp_id")),
                    "clock_in": clock_in,
                    "clock_out": clock_out,
                    "clockin_date": date_key,
                    "clockout_date": date_key,
                    "no_hours": self._calculate_hours(clock_in, clock_out),
                    "shift_id": shift_id
                }

                print(f"[DEBUG] Sending attendance data for employee {payload['emp_code']} (shift {shift_id} date {date_key})")
                logger.info(f"Sending attendance data for employee {payload['emp_code']} (shift {shift_id} date {date_key})")
                success = await self.send_attendance_payload(payload)
                if success and emp_id_int:
                    sent_emp_ids.add(emp_id_int)
                    self._sent_by_date[date_key] = sent_emp_ids
                    # Best-effort: mark synced in DB to avoid future re-pushes
                    try:
                        if date_obj is not None:
                            await self.attendance_service.mark_synced_with_sap(emp_id_int, date_obj)
                    except Exception as mark_err:
                        logger.warning(f"Mark synced failed for emp {emp_id_int} on {date_key}: {mark_err}")
                else:
                    logger.error(f"Stopping sync: server responded with error for employee {emp_id_int} on {date_key}")
                    self._sync_error = True
                    break

        except Exception as e:
            logger.error(f"Error syncing shift {shift_id}: {str(e)}")

    async def schedule_shift_sync(self):
        """Scheduler with static times per shift (will be moved to DB later).

        Times:
          - Shift I: 16:30
          - Shift II: 00:30
          - Shift III: 08:30
          - General (4): 19:00
        """
        while True:
            try:
                now = datetime.now()
                today = now.date()
                # Static schedule per requirement
                shifts = [
                    {"id": 1, "name": "Shift I", "hour": 16, "minute": 30},
                    {"id": 2, "name": "Shift II", "hour": 0,  "minute": 30},
                    {"id": 3, "name": "Shift III","hour": 8,  "minute": 30},
                    {"id": 4, "name": "General", "hour": 19, "minute": 0},
                ]

                for shift in shifts:
                    if now.hour == shift["hour"] and now.minute == shift["minute"]:
                        # Compute sync date (early-morning runs may target previous day)
                        sync_date = today
                        if shift["id"] == 2 and now.hour < 6:
                            sync_date = today - timedelta(days=1)

                        logger.info(f"Starting scheduled sync for {shift['name']} (id {shift['id']}) at {now} for date {sync_date}")
                        await self.sync_shift_attendance(shift["id"], datetime.combine(sync_date, datetime.min.time()))
                        if hasattr(self, '_sync_error') and self._sync_error:
                            logger.error("Aborting all further shift syncs for the day due to server error response.")
                            break
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in schedule_shift_sync: {str(e)}")
                await asyncio.sleep(60)  # Still sleep on error to prevent rapid retries
                
    
    async def _send_to_node_server(self, payload: dict) -> bool:
        """Send attendance data to Node.js server"""
        url = "http://localhost:8081/attendance"   # Node.js server endpoint

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"✅ Successfully sent data to Node server: {payload['emp_code']}")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"❌ Failed to send data (status {response.status}): {text}")
                        return False
        except Exception as e:
            logger.error(f"❌ Error while sending data to Node server: {str(e)}")
            return False

    # ============ LEAVE SYNC METHODS ============

    async def _send_leave_to_node_server(self, payload: dict) -> bool:
        """Send leave data to Node.js server for testing"""
        url = "http://localhost:8081/leave"   # Node.js server endpoint for leave

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"✅ Successfully sent leave to Node server: {payload.get('EMP_CODE')}")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"❌ Failed to send leave (status {response.status}): {text}")
                        return False
        except Exception as e:
            logger.error(f"❌ Error while sending leave to Node server: {str(e)}")
            return False

    def _to_sap_leave_payload(self, leave_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform leave data to SAP format with DD.MM.YYYY dates.
        
        Expected input fields:
        - EMP_CODE, start_date, end_date, no_days, Reason, Status, Absence_type, Absence_text
        """
        out = dict(leave_data)
        # Convert dates from YYYY-MM-DD to DD.MM.YYYY
        if "start_date" in out:
            out["start_date"] = self._to_sap_date(out["start_date"]) if out["start_date"] else out["start_date"]
        if "end_date" in out:
            out["end_date"] = self._to_sap_date(out["end_date"]) if out["end_date"] else out["end_date"]
        return out

    async def _send_leave_to_sap(self, payload: Dict[str, Any]) -> bool:
        """Send a single leave record to SAP."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.sap_leave_url}?sap-client={settings.SAP_CLIENT}",
                    json=payload,
                    auth=aiohttp.BasicAuth(self.sap_auth[0], self.sap_auth[1]),
                    headers={"Content-Type": "application/json", "Accept": "application/json"}
                ) as response:
                    status = response.status
                    body_text = await response.text()
                    if status == 200:
                        try:
                            response_data = None
                            if body_text:
                                response_data = await response.json()
                            if response_data is not None:
                                logger.info(f"SAP leave sync success for emp {payload.get('EMP_CODE')}: {response_data}")
                            else:
                                logger.info(f"SAP leave sync success for emp {payload.get('EMP_CODE')}: non-JSON or empty response: {body_text}")
                        except Exception:
                            logger.info(f"SAP leave sync success for emp {payload.get('EMP_CODE')}: non-JSON response: {body_text}")
                        return True
                    else:
                        logger.error(f"SAP leave sync failed for emp {payload.get('EMP_CODE')} status={status}: {body_text}")
                        return False
        except Exception as e:
            try:
                emp_code = payload.get('EMP_CODE')
            except Exception:
                emp_code = None
            logger.error(f"Error sending leave to SAP for emp {emp_code}: {str(e)}")
            return False

    async def send_leave_payload(self, payload: Dict[str, Any]) -> bool:
        """Send leave payload using settings toggle: 'sap' or 'node'."""
        target = getattr(settings, "SAP_SEND_VIA", "sap").lower()
        # if target == "sap":
        #     sap_payload = self._to_sap_leave_payload(payload)
        #     logger.info(f"SAP leave payload after transformation: {sap_payload}")
        #     return await self._send_leave_to_sap(sap_payload)
        # default to node server for testing
        return await self._send_leave_to_node_server(payload)

    async def sync_leaves_for_date(self, target_date: datetime) -> Dict[str, Any]:
        """Sync approved leaves starting on target_date to SAP.
        
        Fetches leaves where:
        - leave_req_status = 'Approved'
        - leave_req_from_dt = target_date
        - sap_sync_status = 'PENDING'
        
        Sends them to SAP and marks as SENT on success.
        Returns a summary dict.
        """
        from app.database import SessionLocal
        from app.repositories.leave_repo import LeaveRepository
        from app.repositories.leave_type_repo import LeaveTypeRepository

        summary = {
            "date": target_date.strftime("%Y-%m-%d"),
            "total_leaves": 0,
            "sent_success": 0,
            "sent_failed": 0
        }

        db = SessionLocal()
        try:
            leave_repo = LeaveRepository(db)
            leave_type_repo = LeaveTypeRepository(db)

            # Fetch approved leaves starting today that are PENDING sync
            pending_leaves = leave_repo.get_pending_sap_sync(target_date.date())
            summary["total_leaves"] = len(pending_leaves)
            logger.info(f"Found {len(pending_leaves)} approved leaves starting on {target_date.date()} pending SAP sync")

            for leave_req, employee in pending_leaves:
                try:
                    # Calculate number of days
                    no_days = (leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1

                    # Get SAP leave type ID (Absence_type)
                    sap_leave_id = leave_type_repo.get_sap_leave_id(leave_req.leave_req_type)
                    if not sap_leave_id:
                        logger.warning(f"No SAP leave ID mapping for leave type '{leave_req.leave_req_type}', skipping leave_req_id {leave_req.leave_req_id}")
                        summary["sent_failed"] += 1
                        continue

                    # Build SAP payload matching curl format
                    payload = {
                        "EMP_CODE": str(employee.emp_id),
                        "start_date": leave_req.leave_req_from_dt.strftime("%Y-%m-%d"),
                        "end_date": leave_req.leave_req_to_dt.strftime("%Y-%m-%d"),
                        "no_days": str(no_days),
                        "Reason": leave_req.leave_req_reason or "",
                        "Status": leave_req.leave_req_status,
                        "Absence_type": str(sap_leave_id),
                        "Absence_text": leave_req.leave_req_type
                    }

                    # Transform to SAP date format and send
                    sap_payload = self._to_sap_leave_payload(payload)
                    logger.info(f"Sending leave to SAP for emp {employee.emp_id}: {sap_payload}")
                    
                    success = await self.send_leave_payload(payload)
                    if success:
                        # Mark as synced
                        leave_repo.mark_synced_with_sap(leave_req.leave_req_id)
                        summary["sent_success"] += 1
                        logger.info(f"✅ Leave synced for emp {employee.emp_id}, leave_req_id {leave_req.leave_req_id}")
                    else:
                        summary["sent_failed"] += 1
                        logger.error(f"❌ Failed to sync leave for emp {employee.emp_id}, leave_req_id {leave_req.leave_req_id}")

                except Exception as e:
                    summary["sent_failed"] += 1
                    logger.exception(f"Error syncing leave_req_id {leave_req.leave_req_id}: {e}")

        finally:
            db.close()

        return summary

    async def schedule_leave_sync(self):
        """Scheduler to check and sync leaves daily.
        
        Runs every hour and checks if any approved leaves are starting today.
        This ensures leaves get synced on their start date.
        """
        while True:
            try:
                now = datetime.now()
                today = now.date()
                
                # Run leave sync every hour at minute 0 (e.g., 9:00, 10:00, 11:00...)
                if now.minute == 0:
                    logger.info(f"Starting leave sync check for {today}")
                    summary = await self.sync_leaves_for_date(datetime.combine(today, datetime.min.time()))
                    logger.info(f"Leave sync summary: {summary}")
                
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in schedule_leave_sync: {str(e)}")
                await asyncio.sleep(60)