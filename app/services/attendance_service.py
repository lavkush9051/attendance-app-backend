from typing import List, Optional, Dict, Any, Tuple
from datetime import date, time
import logging
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.clock_repo import ClockRepository

logger = logging.getLogger(__name__)
from app.schemas.attendance import (
    AttendanceRegularizationCreate, AttendanceRequestResponse,
    AttendanceRequestDetailResponse, AttendanceStatusUpdate
)
from app.models import AttendanceRequest, Employee

class AttendanceService:
    def __init__(self, attendance_repo: AttendanceRepository, 
                 employee_repo: EmployeeRepository, clock_repo: ClockRepository):
        self.attendance_repo = attendance_repo
        self.employee_repo = employee_repo
        self.clock_repo = clock_repo
        
    async def get_employee_attendance(self, emp_id: int, date: date) -> Optional[Dict[str, Any]]:
        """Get employee attendance for a specific date"""
        try:
            clock_record = self.clock_repo.get_by_employee_and_date(emp_id, date)
            if not clock_record:
                return None
                
            return {
                "clock_in": clock_record.cct_clockin_time,
                "clock_out": clock_record.cct_clockout_time
            }
        except Exception as e:
            logger.error(f"Error getting attendance: {str(e)}")
            return None
            
    async def mark_synced_with_sap(self, emp_id: int, date: date) -> bool:
        """Mark attendance record as synced with SAP"""
        try:
            return self.clock_repo.mark_synced_with_sap(emp_id, date)
        except Exception as e:
            logger.error(f"Error marking sync status: {str(e)}")
            return False

    def create_regularization_request(self, request: AttendanceRegularizationCreate, 
                                    requesting_emp_id: int) -> AttendanceRequestResponse:
        """Create a new attendance regularization request"""
        try:
            # Validate employee exists
            employee = self.employee_repo.get_by_id(requesting_emp_id)
            if not employee:
                raise Exception(f"Employee with ID {requesting_emp_id} not found")

            # Get reporting hierarchy for approvals - L1 only workflow
            hierarchy = self.employee_repo.get_reporting_hierarchy(requesting_emp_id)
            l1_id = hierarchy.get('l1_id')
            # L2 workflow commented for future use
            # l2_id = hierarchy.get('l2_id')

            if not l1_id:
                raise Exception("No L1 manager found for approval workflow")

            # Validate request date is not in future
            if request.request_date > date.today():
                raise Exception("Cannot create regularization for future dates")

            # Check if regularization already exists for this date
            existing_requests = self.attendance_repo.get_by_employee_id(requesting_emp_id)
            for req_tuple in existing_requests:
                existing_req = req_tuple[0]  # AttendanceRequest object
                if (existing_req.art_date == request.request_date and 
                    existing_req.art_status in ['Pending', 'Approved']):
                    raise Exception(f"Regularization request already exists for {request.request_date}")

            # Create the request - L1 only workflow
            attendance_req = self.attendance_repo.create(
                emp_id=requesting_emp_id,
                request_date=request.request_date,
                clock_in=request.clock_in_time,
                clock_out=request.clock_out_time,
                reason=request.reason,
                shift=request.shift,
                l1_id=l1_id,
                # L2 workflow disabled - set to None for L1-only approval
                l2_id=None  # l2_id or l1_id  # Fallback to L1 if no L2 (commented for future use)
            )

            return AttendanceRequestResponse(
                request_id=attendance_req.art_id,
                employee_id=requesting_emp_id,
                employee_name=employee.emp_name,
                request_date=attendance_req.art_date,
                clock_in=attendance_req.art_clockin_time,
                clock_out=attendance_req.art_clockout_time,
                reason=attendance_req.art_reason,
                status=attendance_req.art_status,
                l1_status=attendance_req.art_l1_status,
                l2_status=attendance_req.art_l2_status,
                shift=attendance_req.art_shift,
                created_at=attendance_req.art_id  # Using ID as placeholder
            )

        except Exception as e:
            raise Exception(f"Service error while creating regularization request: {str(e)}")

    def get_employee_requests(self, emp_id: int) -> List[AttendanceRequestResponse]:
        """Get all attendance requests for an employee"""
        try:
            requests_with_employee = self.attendance_repo.get_by_employee_id(emp_id)
            print(f"[DEBUG] Service - requests from repo: {requests_with_employee}")
            print(f"[DEBUG] Service - number of requests: {len(requests_with_employee)}")
            
            return [
                AttendanceRequestResponse(
                    request_id=req[0].art_id,
                    employee_id=req[0].art_emp_id,
                    employee_name=req[1].emp_name,
                    request_date=req[0].art_date,
                    clock_in=req[0].art_clockin_time,
                    clock_out=req[0].art_clockout_time,
                    reason=req[0].art_reason,
                    status=req[0].art_status,
                    l1_status=req[0].art_l1_status,
                    l2_status=req[0].art_l2_status,
                    shift=str(req[0].art_shift) if req[0].art_shift is not None else "",
                    created_at=req[0].art_id,
                    applied_date=getattr(req[0], 'art_applied_date', None)
                ) for req in requests_with_employee
            ]

        except Exception as e:
            raise Exception(f"Service error while fetching employee requests: {str(e)}")

    def get_admin_requests(self, admin_emp_id: int) -> List[AttendanceRequestDetailResponse]:
        """Get attendance requests for admin approval"""
        try:
            requests_with_employee = self.attendance_repo.get_for_admin(admin_emp_id)
            
            results = []
            for req, emp in requests_with_employee:
                # L1-only workflow - only L1 managers can see and approve requests
                can_approve = False
                action_level = None

                if req.art_l1_id == admin_emp_id and req.art_l1_status == "Pending":
                    can_approve = True
                    action_level = "L1"
                # L2 workflow disabled - L2 managers cannot see any requests
                # elif (req.art_l2_id == admin_emp_id and 
                #       req.art_l1_status == "Approved" and 
                #       req.art_l2_status == "Pending"):
                #     can_approve = True
                #     action_level = "L2"

                results.append(AttendanceRequestDetailResponse(
                    request_id=req.art_id,
                    employee_id=req.art_emp_id,
                    employee_name=emp.emp_name,
                    employee_department=emp.emp_department,
                    employee_designation=emp.emp_designation,
                    request_date=req.art_date,
                    clock_in=req.art_clockin_time,
                    clock_out=req.art_clockout_time,
                    reason=req.art_reason,
                    status=req.art_status,
                    l1_status=req.art_l1_status,
                    l2_status=req.art_l2_status,
                    shift=str(req.art_shift) if req.art_shift is not None else "",
                    can_approve=can_approve,
                    action_level=action_level,
                    applied_date=req.art_applied_date,
                    created_at=req.art_id
                ))

            return results

        except Exception as e:
            raise Exception(f"Service error while fetching admin requests: {str(e)}")

    def update_request_status(self, request_id: int, status_update: AttendanceStatusUpdate,
                            admin_emp_id: int) -> AttendanceRequestDetailResponse:
        """Update attendance request status (approve/reject)"""
        try:
            # Get the request
            request = self.attendance_repo.get_by_id(request_id)
            if not request:
                raise Exception(f"Attendance request {request_id} not found")

            # Validate admin permissions - L1 only workflow
            action_level = None
            if request.art_l1_id == admin_emp_id and request.art_l1_status == "Pending":
                action_level = "L1"
            # L2 workflow disabled - L2 managers cannot update any requests
            # elif (request.art_l2_id == admin_emp_id and 
            #       request.art_l1_status == "Approved" and 
            #       request.art_l2_status == "Pending"):
            #     action_level = "L2"
            else:
                raise Exception("Insufficient permissions to update this request")

            # Update status based on action level - L1 only workflow
            if action_level == "L1":
                # L1 approval is final - set all status fields consistently
                final_status = "Approved" if status_update.status == "approve" else "Rejected"
                updated_request = self.attendance_repo.update_status(
                    request_id=request_id,
                    status=final_status,  # Final status since L1 is the only approval level
                    l1_status=final_status,
                    l2_status=final_status  # Set L2 status to match L1 decision
                )
                
                # If L1 approves, push the data to clockin_clockout_tbl
                if status_update.status == "approve":
                    try:
                        # Defensive: ensure shift abbreviation is a plain string
                        shift_abbr = str(updated_request.art_shift) if updated_request.art_shift is not None else None
                        if not shift_abbr:
                            raise Exception("Missing shift abbreviation on attendance request")
                        if not updated_request.art_date:
                            raise Exception("Missing attendance date on attendance request")
                        if not updated_request.art_clockin_time and not updated_request.art_clockout_time:
                            raise Exception("Both clock-in and clock-out times are empty")
                        print(f"[DEBUG] Pushing to clock table: emp={updated_request.art_emp_id}, date={updated_request.art_date}, in={updated_request.art_clockin_time}, out={updated_request.art_clockout_time}, shift={shift_abbr}")
                        self.clock_repo.create_or_update_record(
                            emp_id=updated_request.art_emp_id,
                            record_date=updated_request.art_date,
                            clockin_time=updated_request.art_clockin_time,
                            clockout_time=updated_request.art_clockout_time,
                            shift=shift_abbr
                        )
                    except Exception as clock_error:
                        # Log the error but don't fail the approval process
                        print(f"Warning: Failed to push approved attendance to clock table: {str(clock_error)}")
                        # Could optionally rollback the approval here if this is critical
            # L2 workflow disabled for attendance regularization
            # else:  # L2
            #     final_status = "Approved" if status_update.status == "approve" else "Rejected"
            #     updated_request = self.attendance_repo.update_status(
            #         request_id=request_id,
            #         status=final_status,
            #         l2_status=final_status
            #     )

            if not updated_request:
                raise Exception("Failed to update request status")

            # Get employee details for response
            employee = self.employee_repo.get_by_id(updated_request.art_emp_id)

            return AttendanceRequestDetailResponse(
                request_id=updated_request.art_id,
                employee_id=updated_request.art_emp_id,
                employee_name=employee.emp_name if employee else "Unknown",
                employee_department=employee.emp_department if employee else "Unknown",
                employee_designation=employee.emp_designation if employee else "Unknown",
                request_date=updated_request.art_date,
                clock_in=updated_request.art_clockin_time,
                clock_out=updated_request.art_clockout_time,
                reason=updated_request.art_reason,
                status=updated_request.art_status,
                l1_status=updated_request.art_l1_status,
                l2_status=updated_request.art_l2_status,
                shift=updated_request.art_shift,
                can_approve=False,  # No longer actionable
                action_level=None,
                created_at=updated_request.art_id
            )

        except Exception as e:
            raise Exception(f"Service error while updating request status: {str(e)}")

    def get_request_details(self, request_id: int) -> Optional[AttendanceRequestDetailResponse]:
        """Get detailed information about a specific request"""
        try:
            request = self.attendance_repo.get_by_id(request_id)
            if not request:
                return None

            employee = self.employee_repo.get_by_id(request.art_emp_id)
            if not employee:
                raise Exception(f"Employee {request.art_emp_id} not found")

            return AttendanceRequestDetailResponse(
                request_id=request.art_id,
                employee_id=request.art_emp_id,
                employee_name=employee.emp_name,
                employee_department=employee.emp_department,
                employee_designation=employee.emp_designation,
                request_date=request.art_date,
                clock_in=request.art_clockin_time,
                clock_out=request.art_clockout_time,
                reason=request.art_reason,
                status=request.art_status,
                l1_status=request.art_l1_status,
                l2_status=request.art_l2_status,
                shift=request.art_shift,
                can_approve=False,  # Determined by admin context
                action_level=None,
                created_at=request.art_id
            )

        except Exception as e:
            raise Exception(f"Service error while fetching request details: {str(e)}")

    def delete_request(self, request_id: int, requesting_emp_id: int) -> bool:
        """Delete an attendance request (only by the requesting employee)"""
        try:
            request = self.attendance_repo.get_by_id(request_id)
            if not request:
                raise Exception(f"Attendance request {request_id} not found")

            # Only allow deletion by the requesting employee and only if pending
            if request.art_emp_id != requesting_emp_id:
                raise Exception("Can only delete your own requests")

            if request.art_status != "Pending":
                raise Exception("Cannot delete approved or rejected requests")

            return self.attendance_repo.delete_by_id(request_id)

        except Exception as e:
            raise Exception(f"Service error while deleting request: {str(e)}")

    def get_attendance_analytics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get attendance regularization analytics for admin dashboard"""
        try:
            all_requests = self.attendance_repo.get_all_with_employee_info()
            
            # Filter by date range
            filtered_requests = [
                req for req in all_requests
                if start_date <= req[0].art_date <= end_date
            ]

            total_requests = len(filtered_requests)
            pending_requests = len([req for req in filtered_requests if req[0].art_status == "Pending"])
            approved_requests = len([req for req in filtered_requests if req[0].art_status == "Approved"])
            rejected_requests = len([req for req in filtered_requests if req[0].art_status == "Rejected"])

            # Department wise breakdown
            dept_breakdown = {}
            for req in filtered_requests:
                dept = req[2] or "Unknown"  # emp_department
                if dept not in dept_breakdown:
                    dept_breakdown[dept] = {'total': 0, 'approved': 0, 'rejected': 0, 'pending': 0}
                
                dept_breakdown[dept]['total'] += 1
                if req[0].art_status == "Approved":
                    dept_breakdown[dept]['approved'] += 1
                elif req[0].art_status == "Rejected":
                    dept_breakdown[dept]['rejected'] += 1
                else:
                    dept_breakdown[dept]['pending'] += 1

            return {
                'date_range': {'start': start_date, 'end': end_date},
                'summary': {
                    'total_requests': total_requests,
                    'pending_requests': pending_requests,
                    'approved_requests': approved_requests,
                    'rejected_requests': rejected_requests,
                    'approval_rate': round((approved_requests / total_requests * 100), 2) if total_requests > 0 else 0
                },
                'department_breakdown': dept_breakdown
            }

        except Exception as e:
            raise Exception(f"Service error while generating analytics: {str(e)}")
