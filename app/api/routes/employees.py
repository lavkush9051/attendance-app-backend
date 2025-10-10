from fastapi import APIRouter, Body, Query, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Dict, Any, List, Optional
from app.dependencies import get_current_user_emp_id, validate_admin_access, get_employee_service
from app.auth import get_current_user
from app.services.employee_service import EmployeeService
from app.schemas.employees import EmployeeResponse, WeekoffUpdateRequest

router = APIRouter()

@router.get("/employees")
async def api_get_all_employees(
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    admin_emp_id: int = Depends(validate_admin_access),
    employee_service: EmployeeService = Depends(get_employee_service)
):
    """Get all employees - Admin access required"""
    print(f"[LOG] /employees called by admin {admin_emp_id} with filters: department={department}, status={status}, search={search}")
    try:
        employees = employee_service.get_all_employees()
        
        # Convert to frontend expected format
        formatted_employees = []
        for emp in employees:
            employee_dict = {
                "id": str(emp.emp_id),  # Frontend expects string ID
                "emp_id": str(emp.emp_id),
                "name": emp.emp_name,  # Frontend expects 'name', not 'emp_name'
                "email": emp.emp_email or "",
                "phone": emp.emp_contact or "",
                "department": emp.emp_department or "",
                "designation": emp.emp_designation or "",
                "manager_id": str(emp.emp_l1) if emp.emp_l1 else "",
                "join_date": str(emp.emp_joining_date) if hasattr(emp, 'emp_joining_date') and emp.emp_joining_date else "",
                "status": "active",  # Default status - you may want to add this field to your model
                "shift": getattr(emp, 'emp_shift', 'General'),
                "week_off": emp.emp_weekoff or "Sunday",
                "profile_image": ""  # Add if you have profile images
            }
            formatted_employees.append(employee_dict)
        
        print(f"[LOG] /employees returning {len(formatted_employees)} employees")
        return JSONResponse(content=formatted_employees)
    except Exception as e:
        print(f"[ERROR] /employees exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/employees/{emp_id}")
def get_employee_by_id(
    emp_id: str,  # Frontend sends string IDs
    current_emp_id: int = Depends(get_current_user_emp_id),
    employee_service: EmployeeService = Depends(get_employee_service)
):
    """Get employee details by ID - Users can only access their own data or if they're admin"""
    print(f"[LOG] /employees/{emp_id} called by user {current_emp_id}")
    try:
        emp_id_int = int(emp_id)
        
        # Allow access if requesting own data
        if emp_id_int != current_emp_id:
            # Check if current user has admin access using service
            current_emp = employee_service.get_employee_by_id(current_emp_id)
            if not current_emp or not (current_emp.emp_designation and 
                                      any(role in current_emp.emp_designation.lower() 
                                          for role in ['manager', 'lead', 'head', 'director', 'admin'])):
                print(f"[ERROR] /employees/{emp_id} access denied for user {current_emp_id}")
                raise HTTPException(status_code=403, detail="Access denied - can only view your own profile")
        
        emp = employee_service.get_employee_by_id(emp_id_int)
        if not emp:
            print(f"[ERROR] /employees/{emp_id} employee not found")
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Return in frontend expected format
        employee_data = {
            "id": str(emp.emp_id),
            "emp_id": str(emp.emp_id),
            "name": emp.emp_name,
            "email": emp.emp_email or "",
            "phone": emp.emp_contact or "",
            "department": emp.emp_department or "",
            "designation": emp.emp_designation or "",
            "manager_id": str(emp.emp_l1) if emp.emp_l1 else "",
            "join_date": str(emp.emp_joining_date) if hasattr(emp, 'emp_joining_date') and emp.emp_joining_date else "",
            "status": "active",
            "shift": getattr(emp, "emp_shift", "General"),
            "week_off": emp.emp_weekoff or "Sunday",
            "profile_image": ""
        }
        
        print(f"[LOG] /employees/{emp_id} returning employee data for {emp.emp_name}")
        return JSONResponse(content=employee_data)
    except ValueError:
        print(f"[ERROR] /employees/{emp_id} invalid employee ID format")
        raise HTTPException(status_code=400, detail="Invalid employee ID format")
    except Exception as e:
        print(f"[ERROR] /employees/{emp_id} exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/employees/weekoff")
async def update_employees_weekoff(
    request: Dict[str, Any] = Body(...),
    admin_emp_id: int = Depends(validate_admin_access),
    employee_service: EmployeeService = Depends(get_employee_service)
):
    """Update weekoff for multiple employees - Admin access required"""
    print(f"[LOG] /employees/weekoff called by admin {admin_emp_id} with request: {request}")
    try:
        # Handle both frontend formats
        emp_ids = request.get("emp_ids", request.get("employee_ids", []))
        weekoff = request.get("weekoff", request.get("week_off", ""))
        effective_date = request.get("effective_date")
        
        if not emp_ids or not weekoff:
            raise HTTPException(status_code=400, detail="employee_ids and weekoff are required")
        
        # Convert string IDs to integers if needed
        emp_ids_int = [int(emp_id) if isinstance(emp_id, str) else emp_id for emp_id in emp_ids]
        
        updated_count = 0
        failed_updates = []
        
        for emp_id in emp_ids_int:
            try:
                weekoff_data = WeekoffUpdateRequest(weekoff=weekoff)
                updated_emp = employee_service.update_employee_weekoff(emp_id, weekoff_data)
                if updated_emp:
                    updated_count += 1
                else:
                    failed_updates.append(emp_id)
            except Exception as e:
                print(f"[ERROR] Failed to update weekoff for employee {emp_id}: {str(e)}")
                failed_updates.append(emp_id)
        
        result = {
            "status": "success", 
            "updated": updated_count,
            "failed": len(failed_updates),
            "failed_ids": failed_updates
        }
        print(f"[LOG] /employees/weekoff result: {result}")
        return JSONResponse(content=result)
    except Exception as e:
        print(f"[ERROR] /employees/weekoff exception: {str(e)}")
        return JSONResponse(status_code=500, content={"status": "failed", "error": str(e)})

@router.get("/reporting-levels")
def get_reporting_levels(
    emp_id: Optional[str] = Query(None), 
    l1_id: Optional[str] = Query(None), 
    l2_id: Optional[str] = Query(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    employee_service: EmployeeService = Depends(get_employee_service)
):
    """Get reporting level information for employee hierarchy"""
    print(f"[LOG] /reporting-levels called with emp_id={emp_id}, l1_id={l1_id}, l2_id={l2_id}")
    try:
        # Convert string IDs to integers
        emp_id_int = int(emp_id) if emp_id else current_emp_id
        
        # Get employee to determine their managers
        employee = employee_service.get_employee_by_id(emp_id_int)
        if not employee:
            print(f"[ERROR] Employee {emp_id_int} not found")
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Use employee's actual L1 and L2 if not provided
        l1_id_int = int(l1_id) if l1_id else employee.emp_l1
        l2_id_int = int(l2_id) if l2_id else employee.emp_l2
        
        # Get managers
        l1_manager = employee_service.get_employee_by_id(l1_id_int) if l1_id_int else None
        l2_manager = employee_service.get_employee_by_id(l2_id_int) if l2_id_int else None

        def format_reporting_level(emp, level):
            return {
                "emp_id": str(emp.emp_id),
                "name": emp.emp_name,
                "designation": emp.emp_designation or "",
                "level": level,
                "can_approve_leave": level > 0,  # L1 and L2 can approve leaves
                "can_approve_attendance": level > 0  # L1 and L2 can approve attendance
            }

        reporting_levels = [format_reporting_level(employee, 0)]
        
        if l1_manager:
            reporting_levels.append(format_reporting_level(l1_manager, 1))
        if l2_manager:
            reporting_levels.append(format_reporting_level(l2_manager, 2))

        print(f"[LOG] /reporting-levels returning {len(reporting_levels)} levels")
        return JSONResponse(content=reporting_levels)
    except ValueError as e:
        print(f"[ERROR] /reporting-levels invalid ID format: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except Exception as e:
        print(f"[ERROR] /reporting-levels exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
