from typing import List, Optional, Dict, Any
import logging
from app.repositories.employee_repo import EmployeeRepository
from app.schemas.employees import EmployeeResponse, WeekoffUpdateRequest

logger = logging.getLogger(__name__)

class EmployeeService:
    def __init__(self, employee_repo: EmployeeRepository):
        self.employee_repo = employee_repo
        
    async def get_employees_by_shift(self, shift_id: int) -> List[Dict[str, Any]]:
        """Get all employees assigned to a specific shift"""
        try:
            employees = await self.employee_repo.get_by_shift(shift_id)
            return [emp for emp in employees]  # employees is already a list of dicts
        except Exception as e:
            logger.error(f"Error getting employees by shift: {str(e)}")
            return []

    def get_all_employees(self) -> List[EmployeeResponse]:
        """Get all employees with proper response format"""
        try:
            employees = self.employee_repo.get_all()
            return [EmployeeResponse.from_orm(emp) for emp in employees]
        except Exception as e:
            raise Exception(f"Service error while fetching employees: {str(e)}")
        
    # Api for getting designation wise data...    
    def get_EmpsList_by_Designations(self) -> List[EmployeeResponse]:
        """Get all employees with proper response format"""
        try:
            print("[DEBUG] Fetching employees by specific designations...")
            employees = self.employee_repo.get_emps_by_designations()

            return [EmployeeResponse.from_orm(emp) for emp in employees]
        except Exception as e:
            raise Exception(f"Service error while fetching employees: {str(e)}")

    def get_employee_by_id(self, emp_id: int) -> Optional[EmployeeResponse]:
        """Get employee by ID"""
        try:
            employee = self.employee_repo.get_by_id(emp_id)
            if employee:
                return EmployeeResponse.from_orm(employee)
            return None
        except Exception as e:
            raise Exception(f"Service error while fetching employee {emp_id}: {str(e)}")

    def update_employee_weekoff(self, emp_id: int, weekoff_data: WeekoffUpdateRequest) -> Optional[EmployeeResponse]:
        """Update employee week off days"""
        try:
            # Validate employee exists
            employee = self.employee_repo.get_by_id(emp_id)
            if not employee:
                raise Exception(f"Employee with ID {emp_id} not found")

            # Update weekoff - repository expects a list of emp_ids and returns number of rows updated
            updated_count = self.employee_repo.update_weekoff(
                emp_ids=[emp_id],
                weekoff=weekoff_data.weekoff
            )

            if updated_count and updated_count > 0:
                # Fetch the updated employee record and return a response model
                updated_employee = self.employee_repo.get_by_id(emp_id)
                return EmployeeResponse.from_orm(updated_employee)

            return None

        except Exception as e:
            raise Exception(f"Service error while updating employee weekoff: {str(e)}")

    def get_reporting_hierarchy(self, emp_id: int) -> Dict[str, Any]:
        """Get employee reporting hierarchy"""
        try:
            employee = self.employee_repo.get_by_id(emp_id)
            if not employee:
                raise Exception(f"Employee with ID {emp_id} not found")

            hierarchy = self.employee_repo.get_reporting_hierarchy(emp_id)
            
            return {
                'employee_id': emp_id,
                'employee_name': employee.emp_name,
                'l1_manager': {
                    'id': hierarchy.get('l1_id'),
                    'name': hierarchy.get('l1_name'),
                    'designation': hierarchy.get('l1_designation')
                } if hierarchy.get('l1_id') else None,
                'l2_manager': {
                    'id': hierarchy.get('l2_id'),
                    'name': hierarchy.get('l2_name'),
                    'designation': hierarchy.get('l2_designation')
                } if hierarchy.get('l2_id') else None
            }

        except Exception as e:
            raise Exception(f"Service error while fetching reporting hierarchy: {str(e)}")

    def validate_employee_exists(self, emp_id: int) -> bool:
        """Validate if employee exists"""
        try:
            employee = self.employee_repo.get_by_id(emp_id)
            return employee is not None
        except Exception as e:
            raise Exception(f"Service error while validating employee: {str(e)}")

    def get_employees_by_department(self, department: str) -> List[EmployeeResponse]:
        """Get employees by department"""
        try:
            employees = self.employee_repo.get_all()
            department_employees = [
                emp for emp in employees 
                if emp.emp_department and emp.emp_department.lower() == department.lower()
            ]
            return [EmployeeResponse.from_orm(emp) for emp in department_employees]
        except Exception as e:
            raise Exception(f"Service error while fetching employees by department: {str(e)}")

    def get_employees_by_designation(self, designation: str) -> List[EmployeeResponse]:
        """Get employees by designation"""
        try:
            employees = self.employee_repo.get_all()
            designation_employees = [
                emp for emp in employees 
                if emp.emp_designation and emp.emp_designation.lower() == designation.lower()
            ]
            return [EmployeeResponse.from_orm(emp) for emp in designation_employees]
        except Exception as e:
            raise Exception(f"Service error while fetching employees by designation: {str(e)}")

    def search_employees(self, query: str) -> List[EmployeeResponse]:
        """Search employees by name, department, or designation"""
        try:
            employees = self.employee_repo.get_all()
            query_lower = query.lower()
            
            matching_employees = [
                emp for emp in employees
                if (emp.emp_name and query_lower in emp.emp_name.lower()) or
                   (emp.emp_department and query_lower in emp.emp_department.lower()) or
                   (emp.emp_designation and query_lower in emp.emp_designation.lower()) or
                   (emp.emp_code and query_lower in emp.emp_code.lower())
            ]
            
            return [EmployeeResponse.from_orm(emp) for emp in matching_employees]
        except Exception as e:
            raise Exception(f"Service error while searching employees: {str(e)}")
