from typing import List, Optional, Dict, Any
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.repositories.leave_repo import LeaveRepository
from app.repositories.leave_balance_repo import LeaveBalanceRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.leave_ledger_repo import LeaveLedgerRepository
from app.schemas.leaves import (
    LeaveRequestCreate, LeaveRequestResponse, LeaveRequestDetailResponse,
    LeaveStatusUpdate, LeaveBalanceResponse
)

class LeaveService:
    def __init__(self, leave_repo: LeaveRepository, 
                 leave_balance_repo: LeaveBalanceRepository, 
                 employee_repo: EmployeeRepository,
                 leave_ledger_repo: LeaveLedgerRepository,
                 db: Session):
        self.leave_repo = leave_repo
        self.leave_balance_repo = leave_balance_repo
        self.employee_repo = employee_repo
        self.leave_ledger_repo = leave_ledger_repo
        self.db = db

    def append_timeline_remark(self, leave_req, emp_id: int, action: str, remark: str = None):
        """Append timeline-style remark to existing remarks field"""
        if not remark:
            return
            
        # Format: 12199 (Approved) - "remarks"
        # timeline_entry = f"{emp_id} ({action}) - \"{remark}\""
        emp_name = self.employee_repo.get_by_id(emp_id).emp_name
        emp_id_str = str(emp_id)
        timeline_entry = f"({emp_id_str}) {emp_name} ({action}) - \"{remark}\""
        
        if leave_req.remarks:
            # Add to existing remarks with newline
            leave_req.remarks = f"{leave_req.remarks}\n{timeline_entry}"
        else:
            # First remark
            leave_req.remarks = timeline_entry

    def create_leave_request(self, request: LeaveRequestCreate, 
                           requesting_emp_id: int) -> LeaveRequestResponse:
        """Create a new leave request with complete ledger operations and balance validation"""
        try:
            # Validate employee exists
            employee = self.employee_repo.get_by_id(requesting_emp_id)
            if not employee:
                raise Exception(f"Employee with ID {requesting_emp_id} not found")

            # Validate date range
            if request.from_date > request.to_date:
                raise Exception("From date cannot be after to date")

            if request.from_date < date.today() and request.leave_type.lower() != 'medical leave':
                raise Exception("Cannot apply for past dates")

            # Calculate total days using business days (exclude weekends)
            total_days = self.business_days_inclusive(request.from_date, request.to_date)

            # Check for overlapping leaves
            overlapping = self.leave_repo.get_overlapping_leaves(
                requesting_emp_id, request.from_date, request.to_date
            )
            if overlapping:
                raise Exception(f"Leave request overlaps with existing leave from {overlapping[0].leave_req_from_dt} to {overlapping[0].leave_req_to_dt}")

            # Enhanced balance validation using ledger calculations
            if request.leave_type.lower() != 'sick':
                balance_snapshot = self.get_balance_snapshot(requesting_emp_id, request.leave_type)
                available_balance = balance_snapshot["available"]
                
                if total_days > available_balance:
                    raise Exception(
                        f"Insufficient {request.leave_type} balance. "
                        f"Requested: {total_days} days, Available: {available_balance} days "
                        f"(Accrued: {balance_snapshot['accrued']}, Used: {balance_snapshot['committed']}, "
                        f"Pending: {balance_snapshot['held']})"
                    )

            # Get reporting hierarchy for approvals
            hierarchy = self.employee_repo.get_reporting_hierarchy(requesting_emp_id)
            l1_id = hierarchy.get('l1_id')
            l2_id = hierarchy.get('l2_id')

            if not l1_id:
                raise Exception("No L1 manager found for approval workflow")

            # Create the leave request
            leave_req = self.leave_repo.create(
                emp_id=requesting_emp_id,
                from_date=request.from_date,
                to_date=request.to_date,
                leave_type=request.leave_type,
                reason=request.reason,
                l1_id=l1_id,
                l2_id=l2_id or l1_id,
                total_days=total_days
            )

            # Create HOLD entry in ledger to reserve the leave balance
            self.ledger_hold(requesting_emp_id, request.leave_type, total_days, leave_req.leave_req_id)

            # Commit the transaction
            self.db.commit()
            
            print(f"[LEAVE SERVICE] Leave request created with ledger HOLD: req_id={leave_req.leave_req_id}, "
                  f"emp={requesting_emp_id}, type={request.leave_type}, days={total_days}")

            return LeaveRequestResponse(
                request_id=leave_req.leave_req_id,
                employee_id=requesting_emp_id,
                employee_name=employee.emp_name,
                from_date=leave_req.leave_req_from_dt,
                to_date=leave_req.leave_req_to_dt,
                leave_type=leave_req.leave_req_type,
                reason=leave_req.leave_req_reason,
                total_days=total_days,
                status=leave_req.leave_req_status,
                l1_status=leave_req.leave_req_l1_status,
                l2_status=leave_req.leave_req_l2_status,
                created_at=leave_req.leave_req_id
            )

        except Exception as e:
            # Re-raise the original exception to preserve the error message
            raise

    def get_employee_leave_requests(self, emp_id: int) -> List[LeaveRequestResponse]:
        """Get all leave requests for an employee"""
        try:
            requests_with_employee = self.leave_repo.get_by_employee_id(emp_id)
            
            return [
                LeaveRequestResponse(
                    request_id=req[0].leave_req_id,
                    employee_id=req[0].leave_req_emp_id,
                    employee_name=req[1].emp_name,
                    from_date=req[0].leave_req_from_dt,
                    to_date=req[0].leave_req_to_dt,
                    leave_type=req[0].leave_req_type,
                    reason=req[0].leave_req_reason,
                    total_days=float((req[0].leave_req_to_dt - req[0].leave_req_from_dt).days + 1),
                    status=req[0].leave_req_status,
                    l1_status=req[0].leave_req_l1_status,
                    l2_status=req[0].leave_req_l2_status,
                    created_at=req[0].leave_req_id,
                    remarks=req[0].remarks,
                    applied_date=req[0].leave_req_applied_dt if hasattr(req[0], 'leave_req_applied_dt') and req[0].leave_req_applied_dt else None
                ) for req in requests_with_employee
            ]

        except Exception as e:
            # Re-raise to preserve original error message
            raise

    def get_admin_leave_requests(self, admin_emp_id: int) -> List[LeaveRequestDetailResponse]:
        """Get leave requests for admin approval"""
        try:
            requests_with_employee = self.leave_repo.get_for_admin(admin_emp_id)
            
            results = []
            for req, emp in requests_with_employee:
                # Determine if this admin can take action
                can_approve = False
                action_level = None

                if req.leave_req_l1_id == admin_emp_id and req.leave_req_l1_status == "Pending":
                    can_approve = True
                    action_level = "L1"
                elif (req.leave_req_l2_id == admin_emp_id and 
                      req.leave_req_l1_status == "Approved" and 
                      req.leave_req_l2_status == "Pending"):
                    can_approve = True
                    action_level = "L2"

                # Debug the remarks field
                print(f"[DEBUG] Leave request {req.leave_req_id} remarks: '{req.remarks}'")
                print(f"[DEBUG] Leave request attributes: {[attr for attr in dir(req) if not attr.startswith('_')]}")
                
                results.append(LeaveRequestDetailResponse(
                    request_id=req.leave_req_id,
                    employee_id=req.leave_req_emp_id,
                    employee_name=emp.emp_name,
                    employee_department=emp.emp_department,
                    employee_designation=emp.emp_designation,
                    from_date=req.leave_req_from_dt,
                    to_date=req.leave_req_to_dt,
                    leave_type=req.leave_req_type,
                    reason=req.leave_req_reason,
                    total_days=float((req.leave_req_to_dt - req.leave_req_from_dt).days + 1),
                    status=req.leave_req_status,
                    l1_status=req.leave_req_l1_status,
                    l2_status=req.leave_req_l2_status,
                    can_approve=can_approve,
                    action_level=action_level,
                    created_at=req.leave_req_id,
                    remarks=req.remarks or "",
                    applied_date=req.leave_req_applied_dt if hasattr(req, 'leave_req_applied_dt') and req.leave_req_applied_dt else None,
                ))

            return results

        except Exception as e:
            # Re-raise to preserve original error message
            raise

    def update_leave_status(self, request_id: int, status_update: LeaveStatusUpdate,
                          admin_emp_id: int) -> LeaveRequestDetailResponse:
        """Update leave request status with ledger management"""
        try:
            # Get the request
            request = self.leave_repo.get_by_id(request_id)
            if not request:
                raise Exception(f"Leave request {request_id} not found")

            # Validate admin permissions
            action_level = None
            if request.leave_req_l1_id == admin_emp_id and request.leave_req_l1_status == "Pending":
                action_level = "L1"
            elif (request.leave_req_l2_id == admin_emp_id and 
                  request.leave_req_l1_status == "Approved" and 
                  request.leave_req_l2_status == "Pending"):
                action_level = "L2"
            else:
                raise Exception("Insufficient permissions to update this request")

            # Update status based on action level and manage ledger
            if action_level == "L1":
                updated_request = self.leave_repo.update_status(
                    request_id=request_id,
                    status="HOLD" if status_update.action == "approve" else "RELEASE",
                    l1_status=status_update.action.title()
                )
                
                # If rejected at L1, release the held balance
                if status_update.action == "reject":
                    self.leave_balance_repo.update_used_days(
                        request.leave_req_emp_id, request.leave_req_type, -float((request.leave_req_to_dt - request.leave_req_from_dt).days + 1)
                    )
                    
            else:  # L2 - Final approval
                final_status = "COMMIT" if status_update.action == "approve" else "RELEASE"
                updated_request = self.leave_repo.update_status(
                    request_id=request_id,
                    status=final_status,
                    l2_status=status_update.action.title()
                )
                
                # If rejected at L2, release the held balance
                if status_update.action == "reject":
                    self.leave_balance_repo.update_used_days(
                        request.leave_req_emp_id, request.leave_req_type, -float((request.leave_req_to_dt - request.leave_req_from_dt).days + 1)
                    )

            if not updated_request:
                raise Exception("Failed to update leave status")

            # Get employee details for response
            employee = self.employee_repo.get_by_id(updated_request.leave_req_emp_id)

            return LeaveRequestDetailResponse(
                request_id=updated_request.leave_req_id,
                employee_id=updated_request.leave_req_emp_id,
                employee_name=employee.emp_name if employee else "Unknown",
                employee_department=employee.emp_department if employee else "Unknown",
                employee_designation=employee.emp_designation if employee else "Unknown",
                from_date=updated_request.leave_req_from_dt,
                to_date=updated_request.leave_req_to_dt,
                leave_type=updated_request.leave_req_type,
                reason=updated_request.leave_req_reason,
                total_days=float((updated_request.leave_req_to_dt - updated_request.leave_req_from_dt).days + 1),
                status=updated_request.leave_req_status,
                l1_status=updated_request.leave_req_l1_status,
                l2_status=updated_request.leave_req_l2_status,
                can_approve=False,
                action_level=None,
                created_at=updated_request.leave_req_id
            )

        except Exception as e:
            # Re-raise to preserve original error message
            raise

    def get_employee_leave_balance(self, emp_id: int) -> List[LeaveBalanceResponse]:
        """Get leave balance summary for an employee"""
        try:
            balances = self.leave_balance_repo.get_by_employee_id(emp_id)
            
            result = []
            for balance in balances:
                available = self.leave_balance_repo.get_available_balance(
                    emp_id, balance.lb_leave_type, balance.lb_year
                )
                
                result.append(LeaveBalanceResponse(
                    leave_type=balance.lb_leave_type,
                    allocated_days=balance.lb_allocated_days,
                    used_days=balance.lb_used_days,
                    carried_forward=balance.lb_carried_forward,
                    available_days=available,
                    year=balance.lb_year
                ))
                
            return result

        except Exception as e:
            raise Exception(f"Service error while fetching leave balance: {str(e)}")

    def get_leave_calendar(self, emp_id: int, year: int, month: Optional[int] = None) -> Dict[str, Any]:
        """Get leave calendar view for an employee"""
        try:
            # Get all approved leaves for the period
            start_date = date(year, month or 1, 1)
            if month:
                if month == 12:
                    end_date = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(year, month + 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, 12, 31)

            leave_requests = self.leave_repo.get_by_employee_id(emp_id)
            
            # Filter approved leaves in the date range
            calendar_leaves = []
            for req, emp in leave_requests:
                if (req.leave_req_status in ["COMMIT", "Approved"] and 
                    req.leave_req_from_dt <= end_date and 
                    req.leave_req_to_dt >= start_date):
                    
                    calendar_leaves.append({
                        'from_date': req.leave_req_from_dt,
                        'to_date': req.leave_req_to_dt,
                        'leave_type': req.leave_req_type,
                        'total_days': float((req.leave_req_to_dt - req.leave_req_from_dt).days + 1),
                        'reason': req.leave_req_reason,
                        'status': req.leave_req_status
                    })

            return {
                'employee_id': emp_id,
                'year': year,
                'month': month,
                'date_range': {'start': start_date, 'end': end_date},
                'leaves': calendar_leaves,
                'total_leave_days': sum([leave['total_days'] for leave in calendar_leaves])
            }

        except Exception as e:
            raise Exception(f"Service error while generating leave calendar: {str(e)}")

    def cancel_leave_request(self, request_id: int, requesting_emp_id: int) -> bool:
        """Cancel a leave request and release held balance"""
        try:
            request = self.leave_repo.get_by_id(request_id)
            if not request:
                raise Exception(f"Leave request {request_id} not found")

            # Only allow cancellation by the requesting employee
            if request.leave_req_emp_id != requesting_emp_id:
                raise Exception("Can only cancel your own requests")

            # Only allow cancellation if not yet committed
            if request.leave_req_status == "COMMIT":
                raise Exception("Cannot cancel committed leave requests")

            # Release held balance
            if request.leave_req_status == "HOLD":
                self.leave_balance_repo.update_used_days(
                    request.leave_req_emp_id, request.leave_req_type, -float((request.leave_req_to_dt - request.leave_req_from_dt).days + 1)
                )

            return self.leave_repo.delete_by_id(request_id)

        except Exception as e:
            # Re-raise to preserve original error message
            raise

    def _calculate_leave_days(self, from_date: date, to_date: date) -> float:
        """Calculate number of leave days (can be fractional for half days)"""
        # Simple calculation - can be enhanced with business rules
        delta = to_date - from_date
        return float(delta.days + 1)

    def get_team_leave_calendar(self, manager_emp_id: int, year: int, month: int) -> Dict[str, Any]:
        """Get leave calendar for entire team under a manager"""
        try:
            # Get all employees under this manager
            all_employees = self.employee_repo.get_all()
            team_members = [
                emp for emp in all_employees 
                if emp.l1_manager_id == manager_emp_id or emp.l2_manager_id == manager_emp_id
            ]

            team_leaves = []
            for member in team_members:
                member_calendar = self.get_leave_calendar(member.emp_id, year, month)
                if member_calendar['leaves']:
                    team_leaves.append({
                        'employee_id': member.emp_id,
                        'employee_name': member.emp_name,
                        'department': member.emp_department,
                        'leaves': member_calendar['leaves']
                    })

            return {
                'manager_id': manager_emp_id,
                'year': year,
                'month': month,
                'team_size': len(team_members),
                'team_leaves': team_leaves,
                'total_team_leave_days': sum([
                    sum([leave['total_days'] for leave in member['leaves']]) 
                    for member in team_leaves
                ])
            }

        except Exception as e:
            raise Exception(f"Service error while generating team leave calendar: {str(e)}")

    # ===============================
    # LEDGER OPERATIONS (Old System)
    # ===============================
    
    def business_days_inclusive(self, start_dt: date, end_dt: date) -> float:
        """Calculate business days between dates (excludes weekends)"""
        from datetime import timedelta
        if end_dt < start_dt:
            return 0
        days = 0
        cur = start_dt
        one = timedelta(days=1)
        while cur <= end_dt:
            if cur.weekday() < 5:  # 0=Mon ... 4=Fri
                days += 1
            cur += one
        return float(days)
    
    def get_balance_snapshot(self, emp_id: int, leave_type: str) -> dict:
        """Get current balance snapshot for leave type with ledger calculations"""
        try:
            # Get accrued balance from LeaveBalance table via repository
            accrued = self.leave_balance_repo.get_by_employee_and_type(emp_id, leave_type)
            if accrued is None:
                accrued = 0.0
            
            # Get ledger totals via repository
            ledger_totals = self.leave_ledger_repo.get_balance_totals(emp_id, leave_type)
            held = ledger_totals["held"]
            committed = ledger_totals["committed"]
            
            # Available = accrued - committed - held
            available = float(accrued) - committed - held
            
            return {
                "accrued": round(float(accrued), 2),
                "held": round(held, 2),
                "committed": round(committed, 2),
                "available": round(max(0.0, available), 2)
            }
            
        except Exception as e:
            raise Exception(f"Error getting balance snapshot: {str(e)}")
    
    def ledger_hold(self, emp_id: int, leave_type: str, qty: float, req_id: int):
        """Create a HOLD entry in the leave ledger via repository"""
        try:
            hold_entry = self.leave_ledger_repo.create_hold(emp_id, leave_type, qty, req_id)
            print(f"[LEDGER] HOLD created: emp={emp_id}, type={leave_type}, qty={qty}, req={req_id}")
            return hold_entry
        except Exception as e:
            raise Exception(f"Error creating HOLD ledger entry: {str(e)}")
    
    def ledger_release(self, emp_id: int, leave_type: str, qty: float, req_id: int):
        """Create a RELEASE entry in the leave ledger via repository (with idempotency check)"""
        try:
            release_entry = self.leave_ledger_repo.create_release(emp_id, leave_type, qty, req_id)
            if release_entry:
                print(f"[LEDGER] RELEASE created: emp={emp_id}, type={leave_type}, qty={qty}, req={req_id}")
            else:
                print(f"[LEDGER] RELEASE skipped (already released): emp={emp_id}, req={req_id}")
            return release_entry
        except Exception as e:
            raise Exception(f"Error creating RELEASE ledger entry: {str(e)}")
    
    def ledger_commit(self, emp_id: int, leave_type: str, qty: float, req_id: int):
        """Create a COMMIT entry in the leave ledger via repository (with idempotency check)"""
        try:
            commit_entry = self.leave_ledger_repo.create_commit(emp_id, leave_type, qty, req_id)
            if commit_entry:
                print(f"[LEDGER] COMMIT created: emp={emp_id}, type={leave_type}, qty={qty}, req={req_id}")
            else:
                print(f"[LEDGER] COMMIT skipped (already exists): emp={emp_id}, req={req_id}")
            return commit_entry
        except Exception as e:
            raise Exception(f"Error creating COMMIT ledger entry: {str(e)}")
    
    def get_ledger_audit_trail(self, req_id: int) -> List[Dict[str, Any]]:
        """Get complete audit trail for a leave request via repository"""
        try:
            return self.leave_ledger_repo.get_audit_trail(req_id)
        except Exception as e:
            raise Exception(f"Error getting audit trail: {str(e)}")
    
    def verify_ledger_integrity(self, req_id: int) -> Dict[str, Any]:
        """Verify ledger integrity for a leave request via repository"""
        try:
            return self.leave_ledger_repo.verify_ledger_integrity(req_id)
        except Exception as e:
            raise Exception(f"Error verifying ledger integrity: {str(e)}")
    
    def authorize_balance_access(self, requesting_emp_id: int, target_emp_id: int) -> bool:
        """Check if requesting employee can access target employee's balance"""
        try:
            # Users can always view their own balance
            if requesting_emp_id == target_emp_id:
                return True
            
            # Check if requesting user is L1 or L2 manager for target employee
            target_employee = self.employee_repo.get_by_id(target_emp_id)
            if not target_employee:
                return False
            
            return requesting_emp_id in [target_employee.emp_l1_id, target_employee.emp_l2_id]
        except Exception as e:
            raise Exception(f"Error checking balance access authorization: {str(e)}")
    
    def get_employee_balance_snapshot(self, emp_id: int, requesting_emp_id: int, leave_type: Optional[str] = None) -> Dict[str, Any]:
        """Get balance snapshot with authorization check"""
        try:
            # Authorization check
            if not self.authorize_balance_access(requesting_emp_id, emp_id):
                raise Exception("Not authorized to view this employee's balance")
            
            if leave_type:
                # Get specific leave type balance
                snapshot = self.get_balance_snapshot(emp_id, leave_type)
                return {
                    "employee_id": emp_id,
                    "leave_type": leave_type,
                    "balance": snapshot
                }
            else:
                # Get all leave types for the employee
                leave_balance_record = self.leave_balance_repo.get_by_employee_id(emp_id)
                if not leave_balance_record:
                    return {
                        "employee_id": emp_id,
                        "balances": {}
                    }
                
                # Get available leave types from leave balance columns
                from app.repositories.leave_balance_repo import LEAVE_COL_MAP
                balances = {}
                for leave_type in LEAVE_COL_MAP.keys():
                    balances[leave_type] = self.get_balance_snapshot(emp_id, leave_type)
                
                return {
                    "employee_id": emp_id,
                    "balances": balances
                }
                
        except Exception as e:
            raise Exception(f"Error getting employee balance snapshot: {str(e)}")
    
    # ===============================
    # L1/L2 APPROVAL WORKFLOW  
    # ===============================
    
    def l1_approve_leave_request(self, req_id: int, approver_id: int, remarks: str = None) -> dict:
        """L1 manager approves leave request"""
        try:
            # Get leave request via repository
            leave_req = self.leave_repo.get_by_id(req_id)
            if not leave_req:
                raise Exception(f"Leave request {req_id} not found")
            
            # Verify approver is L1 manager
            if leave_req.leave_req_l1_id != approver_id:
                raise Exception("Not authorized to approve this request (L1 mismatch)")
            
            # Check current status
            if leave_req.leave_req_l1_status != "Pending":
                raise Exception(f"Leave request already processed by L1. Current status: {leave_req.leave_req_l1_status}")
            
            # Check if L2 approval is needed
            if leave_req.leave_req_l2_id and leave_req.leave_req_l2_id != leave_req.leave_req_l1_id:
                # L2 approval needed - update L1 status and overall status to "L1 Approved"
                self.leave_repo.update_status(req_id, "L1 Approved", "Approved", None)
                # Add L1 remarks in timeline format
                self.append_timeline_remark(leave_req, approver_id, "Approved", remarks)
                self.db.commit()
                message = "Approved by L1. Waiting for L2 approval."
            else:
                # No L2 needed or L1=L2 - fully approve
                self.leave_repo.update_status(req_id, "Approved", "Approved", "Approved")
                
                # COMMIT the leave in ledger (final approval)
                total_days = float((leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1)
                self.ledger_commit(
                    leave_req.leave_req_emp_id, 
                    leave_req.leave_req_type, 
                    total_days, 
                    req_id
                )
                
                # Add L1 remarks in timeline format
                self.append_timeline_remark(leave_req, approver_id, "Approved", remarks)
                self.db.commit()
                
                message = "Fully approved. Leave committed."
            
            # Get updated request for response
            updated_req = self.leave_repo.get_by_id(req_id)
            
            return {
                "status": "success",
                "message": message,
                "l1_status": updated_req.leave_req_l1_status,
                "l2_status": updated_req.leave_req_l2_status,
                "overall_status": updated_req.leave_req_status
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error in L1 approval: {str(e)}")
    
    def l2_approve_leave_request(self, req_id: int, approver_id: int, remarks: str = None) -> dict:
        """L2 manager approves leave request"""
        try:
            # Get leave request via repository
            leave_req = self.leave_repo.get_by_id(req_id)
            if not leave_req:
                raise Exception(f"Leave request {req_id} not found")
            
            # Verify approver is L2 manager
            if leave_req.leave_req_l2_id != approver_id:
                raise Exception("Not authorized to approve this request (L2 mismatch)")
            
            # Check L1 is approved first
            if leave_req.leave_req_l1_status != "Approved":
                raise Exception("L1 approval required before L2 approval")
            
            # Check current L2 status
            if leave_req.leave_req_l2_status != "Pending":
                raise Exception(f"Leave request already processed by L2. Current status: {leave_req.leave_req_l2_status}")
            
            # Update L2 status and overall status via repository
            self.leave_repo.update_status(req_id, "Approved", None, "Approved")
            
            # COMMIT the leave in ledger (final approval)
            total_days = float((leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1)
            self.ledger_commit(
                leave_req.leave_req_emp_id, 
                leave_req.leave_req_type, 
                total_days, 
                req_id
            )
            
            # Add L2 remarks in timeline format
            self.append_timeline_remark(leave_req, approver_id, "Approved", remarks)
            self.db.commit()
            
            # Get updated request for response
            updated_req = self.leave_repo.get_by_id(req_id)
            
            return {
                "status": "success",
                "message": "Fully approved by L2. Leave committed.",
                "l1_status": updated_req.leave_req_l1_status,
                "l2_status": updated_req.leave_req_l2_status,
                "overall_status": updated_req.leave_req_status
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error in L2 approval: {str(e)}")
    
    def reject_leave_request(self, req_id: int, approver_id: int, remarks: str) -> dict:
        """Reject leave request (L1 or L2)"""
        try:
            from app.models import LeaveRequest
            
            # Get leave request
            leave_req = self.db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == req_id).first()
            if not leave_req:
                raise Exception(f"Leave request {req_id} not found")
            
            # Verify approver is L1 or L2 manager
            if approver_id not in [leave_req.leave_req_l1_id, leave_req.leave_req_l2_id]:
                raise Exception("Not authorized to reject this request")
            
            # Check if already processed
            if leave_req.leave_req_status == "Rejected":
                raise Exception(f"Leave request already rejected")
            
            # If approved, check if leave start date is greater than today (allow future cancellation)
            if leave_req.leave_req_status == "Approved":
                from datetime import date
                if leave_req.leave_req_from_dt <= date.today():
                    raise Exception("Cannot reject approved leave that has already started or starts today")
            
            # Update status based on who is rejecting
            if approver_id == leave_req.leave_req_l1_id:
                leave_req.leave_req_l1_status = "Rejected"
                self.append_timeline_remark(leave_req, approver_id, "Rejected", remarks)
            else:  # L2 rejection
                leave_req.leave_req_l2_status = "Rejected"
                self.append_timeline_remark(leave_req, approver_id, "Rejected", remarks)
            
            leave_req.leave_req_status = "Rejected"
            
            # RELEASE the held balance back to available
            total_days = float((leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1)
            self.ledger_release(
                leave_req.leave_req_emp_id, 
                leave_req.leave_req_type, 
                total_days, 
                req_id
            )
            
            self.db.commit()
            
            return {
                "status": "success",
                "message": "Leave request rejected. Balance released.",
                "l1_status": leave_req.leave_req_l1_status,
                "l2_status": leave_req.leave_req_l2_status,
                "overall_status": leave_req.leave_req_status
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error rejecting leave request: {str(e)}")
    
    def cancel_leave_request(self, req_id: int, emp_id: int, reason: str) -> dict:
        """Employee cancels their own leave request"""
        try:
            from app.models import LeaveRequest
            
            # Get leave request
            leave_req = self.db.query(LeaveRequest).filter(LeaveRequest.leave_req_id == req_id).first()
            if not leave_req:
                raise Exception(f"Leave request {req_id} not found")
            
            # Verify ownership
            if leave_req.leave_req_emp_id != emp_id:
                raise Exception("Can only cancel your own leave request")
            
            # Check if cancellable
            if leave_req.leave_req_status in ["Rejected", "Cancelled"]:
                raise Exception(f"Cannot cancel request with status: {leave_req.leave_req_status}")
            
            # Check if leave start date is greater than today
            from datetime import date
            if leave_req.leave_req_from_dt <= date.today():
                raise Exception("Cannot cancel leave request as leave start date must be greater than today")
            
            # Update status
            leave_req.leave_req_status = "Cancelled"
            self.append_timeline_remark(leave_req, emp_id, "Cancelled", reason)
            
            # RELEASE the balance
            total_days = float((leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1)
            if leave_req.leave_req_status == "Approved":
                # If was approved, reverse the COMMIT with RELEASE
                self.ledger_release(
                    leave_req.leave_req_emp_id, 
                    leave_req.leave_req_type, 
                    total_days, 
                    req_id
                )
            else:
                # If was pending, just release the HOLD
                self.ledger_release(
                    leave_req.leave_req_emp_id, 
                    leave_req.leave_req_type, 
                    total_days, 
                    req_id
                )
            
            self.db.commit()
            
            return {
                "status": "success",
                "message": "Leave request cancelled successfully. Balance released.",
                "overall_status": leave_req.leave_req_status
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error cancelling leave request: {str(e)}")
    
    def l1_cancel_leave_request(self, req_id: int, approver_id: int, reason: str = None) -> dict:
        """L1 manager cancels/rejects leave request"""
        try:
            # Get leave request via repository
            leave_req = self.leave_repo.get_by_id(req_id)
            if not leave_req:
                raise Exception(f"Leave request {req_id} not found")
            
            # Verify approver is L1 manager
            if leave_req.leave_req_l1_id != approver_id:
                raise Exception("Not authorized to cancel this request (L1 mismatch)")
            
            # Check if already processed
            if leave_req.leave_req_status in ["Rejected", "Cancelled"]:
                raise Exception(f"Cannot cancel request with status: {leave_req.leave_req_status}")
            
            # Check if leave start date is greater than today
            from datetime import date
            if leave_req.leave_req_from_dt <= date.today():
                raise Exception("Cannot cancel leave request as leave start date must be greater than today")
            
            # Update status - L1 rejection means overall rejection
            leave_req.leave_req_l1_status = "Rejected"
            leave_req.leave_req_status = "Rejected"
            self.append_timeline_remark(leave_req, approver_id, "Cancelled", reason)
            
            # RELEASE the held balance
            total_days = float((leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1)
            self.ledger_release(
                leave_req.leave_req_emp_id, 
                leave_req.leave_req_type, 
                total_days, 
                req_id
            )
            
            self.db.commit()
            
            # Get updated request for response
            updated_req = self.leave_repo.get_by_id(req_id)
            
            return {
                "status": "success",
                "message": "Leave request cancelled by L1 manager. Balance released.",
                "l1_status": updated_req.leave_req_l1_status,
                "l2_status": updated_req.leave_req_l2_status,
                "overall_status": updated_req.leave_req_status
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error in L1 cancellation: {str(e)}")
    
    def l2_cancel_leave_request(self, req_id: int, approver_id: int, reason: str = None) -> dict:
        """L2 manager cancels/rejects leave request"""
        try:
            # Get leave request via repository
            leave_req = self.leave_repo.get_by_id(req_id)
            if not leave_req:
                raise Exception(f"Leave request {req_id} not found")
            
            # Verify approver is L2 manager
            if leave_req.leave_req_l2_id != approver_id:
                raise Exception("Not authorized to cancel this request (L2 mismatch)")
            
            # Check if already processed
            if leave_req.leave_req_status in ["Rejected", "Cancelled"]:
                raise Exception(f"Cannot cancel request with status: {leave_req.leave_req_status}")
            
            # Check if leave start date is greater than today
            from datetime import date
            if leave_req.leave_req_from_dt <= date.today():
                raise Exception("Cannot cancel leave request as leave start date must be greater than today")
            
            # Update status - L2 rejection means overall rejection
            leave_req.leave_req_l2_status = "Rejected"
            leave_req.leave_req_status = "Rejected"
            self.append_timeline_remark(leave_req, approver_id, "Cancelled", reason)
            
            # RELEASE the held balance
            total_days = float((leave_req.leave_req_to_dt - leave_req.leave_req_from_dt).days + 1)
            self.ledger_release(
                leave_req.leave_req_emp_id, 
                leave_req.leave_req_type, 
                total_days, 
                req_id
            )
            
            self.db.commit()
            
            # Get updated request for response
            updated_req = self.leave_repo.get_by_id(req_id)
            
            return {
                "status": "success",
                "message": "Leave request cancelled by L2 manager. Balance released.",
                "l1_status": updated_req.leave_req_l1_status,
                "l2_status": updated_req.leave_req_l2_status,
                "overall_status": updated_req.leave_req_status
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error in L2 cancellation: {str(e)}")
