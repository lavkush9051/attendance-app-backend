from typing import List, Optional, Dict, Any
from app.repositories.employee_repo import EmployeeRepository
from app.schemas.employees import EmployeeResponse, WeekoffUpdateRequest

class EmployeeService:
    def __init__(self, employee_repo: EmployeeRepository):
        self.employee_repo = employee_repo

    def get_all_employees(self) -> List[EmployeeResponse]:
        """Get all employees with proper response format"""
        try:
            employees = self.employee_repo.get_all()
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

            # Update weekoff
            updated_employee = self.employee_repo.update_weekoff(
                emp_id=emp_id,
                weekoff=weekoff_data.weekoff
            )

            if updated_employee:
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
