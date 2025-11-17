# helper to run hardcoded sync for testing
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

from app.services.sap_sync_service import SAPSyncService

logger = logging.getLogger(__name__)


async def run_test_sync(sap_service: SAPSyncService, test_date: str = "2025-10-04") -> dict:
    """Run a one-time hardcoded sync across 4 shifts for the provided test_date.

    Returns a summary dict with counts for monitoring / API response.
    """
    shifts = [1, 2, 3, 4]
    sent_emp_ids = set()
    summary = {
        "date": test_date,
        "shifts_processed": 0,
        "total_rows": 0,
        "distinct_employees_sent": 0,
        "records_attempted": 0,
        "records_success": 0,
        "records_failed": 0,
        "duplicates_skipped": 0,
        "missing_times_skipped": 0
    }

    for shift_id in shifts:
        try:
            logger.info(f"[hardcoded-sync] Running for shift={shift_id} date={test_date}")
            rows = await sap_service.get_employees_by_shift_and_date(shift_id, test_date)
            summary["shifts_processed"] += 1
            summary["total_rows"] += len(rows)
            logger.info(f"[hardcoded-sync] found {len(rows)} rows for shift {shift_id}")

            for row in rows:
                summary["records_attempted"] += 1
                try:
                    emp_id_int = int(row.get("emp_id")) if row.get("emp_id") is not None else None
                except Exception:
                    emp_id_int = None

                if emp_id_int in sent_emp_ids:
                    summary["duplicates_skipped"] += 1
                    logger.info(f"[hardcoded-sync] skip duplicate emp {emp_id_int}")
                    continue

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
                    summary["missing_times_skipped"] += 1
                    logger.info(f"[hardcoded-sync] skipping emp {row.get('emp_code')} missing times")
                    continue

                payload = {
                    "emp_id": emp_id_int,
                    "emp_code": str(row.get("emp_code") or row.get("emp_id")),
                    "clock_in": clock_in,
                    "clock_out": clock_out,
                    "clockin_date": test_date,
                    "clockout_date": test_date,
                    "no_hours": sap_service._calculate_hours(clock_in, clock_out),
                    "shift_id": shift_id
                }

                logger.info(f"[hardcoded-sync] sending payload for emp {payload['emp_code']}")
                success = await sap_service.send_attendance_payload(payload)
                if success and emp_id_int:
                    sent_emp_ids.add(emp_id_int)
                    summary["records_success"] += 1
                    summary["distinct_employees_sent"] = len(sent_emp_ids)
                    # Best-effort persisted dedup
                    try:
                        from datetime import datetime as _dt
                        date_obj = _dt.strptime(test_date, "%Y-%m-%d").date()
                        await sap_service.attendance_service.mark_synced_with_sap(emp_id_int, date_obj)
                    except Exception as mark_err:
                        logger.warning(f"[hardcoded-sync] mark synced failed for emp {emp_id_int} on {test_date}: {mark_err}")
                else:
                    summary["records_failed"] += 1
                    logger.error(f"[hardcoded-sync] failed to send for emp {emp_id_int}, stopping immediately")
                    return summary

        except Exception as e:
            logger.exception(f"[hardcoded-sync] error for shift {shift_id}: {e}")
    return summary


if __name__ == '__main__':
    print('This helper expects an application context to construct SAPSyncService.\n'
          'Import run_test_sync and call it from your app (where DB/session/services are configured).')
