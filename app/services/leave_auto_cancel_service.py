"""
Auto-cancellation service for pending leaves.

This service runs daily to automatically cancel leave requests that are:
- Still in 'Pending' status
- Start date has arrived (leave_req_from_dt = today)

When cancelled, the held leave balance is released back to the employee.
"""
import asyncio
import logging
from datetime import datetime, date
from typing import Dict, Any
from app.database import SessionLocal
from app.repositories.leave_repo import LeaveRepository
from app.repositories.leave_balance_repo import LeaveBalanceRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.leave_ledger_repo import LeaveLedgerRepository
from app.services.leave_service import LeaveService

logger = logging.getLogger(__name__)


class LeaveAutoCancelService:
    """Service to automatically cancel pending leaves when their start date arrives."""

    def __init__(self):
        pass

    async def auto_cancel_pending_leaves(self, target_date: date = None) -> Dict[str, Any]:
        """Cancel all pending leaves that start on target_date (defaults to today).
        
        For each cancelled leave:
        1. Change leave_req_status from 'Pending' to 'Cancelled'
        2. Release the held balance back via ledger_release
        
        Returns summary of cancellations.
        """
        if target_date is None:
            target_date = date.today()

        summary = {
            "date": target_date.isoformat(),
            "total_pending": 0,
            "cancelled": 0,
            "failed": 0,
            "errors": []
        }

        db = SessionLocal()
        try:
            leave_repo = LeaveRepository(db)
            leave_balance_repo = LeaveBalanceRepository(db)
            employee_repo = EmployeeRepository(db)
            leave_ledger_repo = LeaveLedgerRepository(db)
            leave_service = LeaveService(
                leave_repo, leave_balance_repo, employee_repo, leave_ledger_repo, db
            )

            # Find all pending leaves starting on target_date
            from app.models import LeaveRequest
            pending_leaves = db.query(LeaveRequest).filter(
                LeaveRequest.leave_req_status == "Pending",
                LeaveRequest.leave_req_from_dt == target_date
            ).all()

            summary["total_pending"] = len(pending_leaves)
            logger.info(f"Found {len(pending_leaves)} pending leaves starting on {target_date}")

            for leave_req in pending_leaves:
                try:
                    # Calculate leave days
                    total_days = float((leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1)

                    # Update status to Cancelled
                    leave_req.leave_req_status = "Cancelled"
                    leave_req.leave_req_l1_status = "Cancelled"
                    leave_req.leave_req_l2_status = "Cancelled"
                    
                    # Add system remark
                    if leave_req.remarks:
                        leave_req.remarks += f"\nSystem (Auto-Cancelled) - Leave not approved before start date"
                    else:
                        leave_req.remarks = "System (Auto-Cancelled) - Leave not approved before start date"
                    
                    db.commit()

                    # Release the held balance back to employee
                    try:
                        leave_service.ledger_release(
                            emp_id=leave_req.leave_req_emp_id,
                            leave_type=leave_req.leave_req_type,
                            qty=total_days,
                            req_id=leave_req.leave_req_id
                        )
                        logger.info(
                            f"✅ Auto-cancelled leave_req_id={leave_req.leave_req_id}, "
                            f"emp={leave_req.leave_req_emp_id}, type={leave_req.leave_req_type}, "
                            f"days={total_days}"
                        )
                        summary["cancelled"] += 1
                    except Exception as ledger_err:
                        # If ledger release fails, log but don't rollback the cancellation
                        logger.error(
                            f"⚠️ Leave cancelled but ledger release failed for req_id={leave_req.leave_req_id}: {ledger_err}"
                        )
                        summary["errors"].append({
                            "leave_req_id": leave_req.leave_req_id,
                            "error": f"Ledger release failed: {str(ledger_err)}"
                        })
                        summary["cancelled"] += 1  # Still count as cancelled

                except Exception as e:
                    db.rollback()
                    summary["failed"] += 1
                    error_msg = f"Failed to cancel leave_req_id={leave_req.leave_req_id}: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    summary["errors"].append({
                        "leave_req_id": leave_req.leave_req_id,
                        "error": str(e)
                    })

        finally:
            db.close()

        logger.info(f"Auto-cancel summary: {summary}")
        return summary

    async def schedule_auto_cancel(self):
        """Scheduler that runs daily at 00:01 to cancel pending leaves."""
        while True:
            try:
                now = datetime.now()
                
                # Run at 00:01 (1 minute after midnight)
                if now.hour == 0 and now.minute == 1:
                    logger.info(f"Starting auto-cancel check for {now.date()}")
                    summary = await self.auto_cancel_pending_leaves()
                    logger.info(f"Auto-cancel completed: {summary}")
                
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in schedule_auto_cancel: {str(e)}")
                await asyncio.sleep(60)
