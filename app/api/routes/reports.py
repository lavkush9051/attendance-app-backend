from fastapi import APIRouter, Query, Response, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from app.dependencies import (
    get_current_user_emp_id, 
    validate_admin_access,
    get_attendance_service,
    get_employee_service
)
from app.services.attendance_service import AttendanceService
from app.services.employee_service import EmployeeService
import pandas as pd
import io

router = APIRouter()

@router.get("/reporting-levels")
def get_reporting_levels(
    emp_id: Optional[str] = Query(None),
    l1_id: Optional[str] = Query(None),
    l2_id: Optional[str] = Query(None),
    current_emp_id: int = Depends(get_current_user_emp_id),
    employee_service: EmployeeService = Depends(get_employee_service)
):
    """Get reporting hierarchy and approval levels"""
    print(f"[LOG] /reporting-levels called by user {current_emp_id} with emp_id={emp_id}, l1_id={l1_id}, l2_id={l2_id}")
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

@router.get("/reports/attendance")
def get_attendance_report(
    emp_id: Optional[str] = Query(None),
    month: str = Query(...),
    year: str = Query(...),
    format: Optional[str] = Query("json"),
    current_emp_id: int = Depends(get_current_user_emp_id),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    employee_service: EmployeeService = Depends(get_employee_service)
):
    """Get attendance report data or download as Excel/PDF"""
    print(f"[LOG] /reports/attendance called by user {current_emp_id} for emp_id={emp_id}, month={month}, year={year}, format={format}")
    try:
        # If emp_id is not provided, use current user's ID
        emp_id_int = int(emp_id) if emp_id else current_emp_id
        month_int = int(month)
        year_int = int(year)
        
        # Check if user has permission to access this employee's data
        if emp_id_int != current_emp_id:
            # Check if current user is admin using service layer
            current_emp = employee_service.get_employee_by_id(current_emp_id)
            if not current_emp or not (current_emp.emp_designation and 
                                      any(role in current_emp.emp_designation.lower() 
                                          for role in ['manager', 'lead', 'head', 'director', 'admin'])):
                print(f"[ERROR] /reports/attendance access denied for user {current_emp_id} requesting emp_id {emp_id_int}")
                raise HTTPException(
                    status_code=403,
                    detail="Access denied - can only access your own reports"
                )
        
        if format == "json":
            # Return JSON data for frontend using actual attendance service
            employee = employee_service.get_employee_by_id(emp_id_int)
            
            # Get attendance data for the month using clock service
            from datetime import datetime, date, timedelta
            from app.services.clock_service import ClockService
            from app.dependencies import get_clock_service
            
            # Calculate date range for the month
            start_date = date(year_int, month_int, 1)
            # Get last day of month
            if month_int == 12:
                end_date = date(year_int + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year_int, month_int + 1, 1) - timedelta(days=1)
            
            # Get clock service instance
            from app.database import get_db
            from app.repositories.clock_repo import ClockRepository
            db = next(get_db())
            clock_repo = ClockRepository(db)
            clock_service = ClockService(clock_repo)
            
            # Get attendance records
            records = clock_service.get_employee_attendance_records(emp_id_int, start_date, end_date)
            
            daily_records = []
            present_days = 0
            total_working_days = 0
            
            # Calculate working days and build daily records
            current_date = start_date
            while current_date <= end_date:
                weekday = current_date.weekday()
                is_working_day = weekday < 5  # Monday=0, Friday=4 (exclude Sat/Sun)
                
                if is_working_day:
                    total_working_days += 1
                    
                    # Find attendance record for this date
                    record = next((r for r in records if r.date == current_date), None)
                    
                    if record:
                        present_days += 1
                        clock_in = record.clockin_time.strftime("%H:%M") if record.clockin_time else ""
                        clock_out = record.clockout_time.strftime("%H:%M") if record.clockout_time else ""
                        
                        # Calculate working hours
                        working_hours = 0
                        if record.clockin_time and record.clockout_time:
                            t1 = datetime.combine(datetime.today(), record.clockin_time)
                            t2 = datetime.combine(datetime.today(), record.clockout_time)
                            working_hours = (t2 - t1).total_seconds() / 3600
                        
                        daily_records.append({
                            "date": current_date.strftime("%Y-%m-%d"),
                            "status": "present",
                            "clock_in": clock_in,
                            "clock_out": clock_out,
                            "working_hours": round(working_hours, 2) if working_hours else 0,
                            "late_minutes": 0,  # Can be calculated if needed
                            "early_departure_minutes": 0,  # Can be calculated if needed
                            "remarks": record.shift or ""
                        })
                    else:
                        daily_records.append({
                            "date": current_date.strftime("%Y-%m-%d"),
                            "status": "absent",
                            "clock_in": "",
                            "clock_out": "",
                            "working_hours": 0,
                            "late_minutes": 0,
                            "early_departure_minutes": 0,
                            "remarks": ""
                        })
                
                current_date += timedelta(days=1)
            
            absent_days = total_working_days - present_days
            
            report_data = {
                "employee": {
                    "emp_id": str(emp_id_int),
                    "name": employee.emp_name if employee else "Unknown",
                    "department": employee.emp_department if employee else "",
                    "designation": employee.emp_designation if employee else ""
                },
                "period": {
                    "month": month,
                    "year": year
                },
                "summary": {
                    "total_working_days": total_working_days,
                    "present_days": present_days,
                    "absent_days": absent_days,
                    "leave_days": 0,  # Would need leave service integration
                    "late_days": 0,  # Would need calculation
                    "early_departure_days": 0  # Would need calculation
                },
                "daily_records": daily_records
            }
            print(f"[LOG] /reports/attendance returning JSON report for emp {emp_id_int}: {present_days}/{total_working_days} present")
            return JSONResponse(content=report_data)
        
        elif format == "excel":
            # Return Excel file download with actual attendance data
            try:
                employee = employee_service.get_employee_by_id(emp_id_int)
                
                # Calculate date range for the month
                from datetime import datetime, date, timedelta
                from app.services.clock_service import ClockService
                
                start_date = date(year_int, month_int, 1)
                # Get last day of month
                if month_int == 12:
                    end_date = date(year_int + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(year_int, month_int + 1, 1) - timedelta(days=1)
                
                # Get clock service instance
                from app.database import get_db
                from app.repositories.clock_repo import ClockRepository
                db = next(get_db())
                clock_repo = ClockRepository(db)
                clock_service = ClockService(clock_repo)
                
                # Get attendance records
                records = clock_service.get_employee_attendance_records(emp_id_int, start_date, end_date)
                
                # Build Excel data
                excel_data = []
                current_date = start_date
                
                while current_date <= end_date:
                    weekday = current_date.weekday()
                    is_working_day = weekday < 5  # Monday=0, Friday=4 (exclude Sat/Sun)
                    
                    if is_working_day:
                        # Find attendance record for this date
                        record = next((r for r in records if r.date == current_date), None)
                        
                        if record:
                            clock_in = record.clockin_time.strftime("%H:%M") if record.clockin_time else "-"
                            clock_out = record.clockout_time.strftime("%H:%M") if record.clockout_time else "-"
                            status = "Present"
                            shift = record.shift or "-"
                        else:
                            clock_in = "-"
                            clock_out = "-"
                            status = "Absent"
                            shift = "-"
                        
                        excel_data.append({
                            "Emp_ID": str(emp_id_int),
                            "Employee_Name": employee.emp_name if employee else "Unknown",
                            "Date": current_date.strftime("%Y-%m-%d"),
                            "Status": status,
                            "Clock_In": clock_in,
                            "Clock_Out": clock_out,
                            "Shift": shift,
                            "Designation": employee.emp_designation if employee else "-"
                        })
                    
                    current_date += timedelta(days=1)
                
                df = pd.DataFrame(excel_data)
                
                # Generate Excel file
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Attendance Report')
                    
                    # Get the workbook and worksheet objects
                    workbook = writer.book
                    worksheet = writer.sheets['Attendance Report']
                    
                    # Add some formatting
                    header_format = workbook.add_format({
                        'bold': True,
                        'text_wrap': True,
                        'valign': 'top',
                        'fg_color': '#D7E4BC',
                        'border': 1
                    })
                    
                    # Write headers with formatting
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    # Auto-adjust column widths
                    for col_num, col_name in enumerate(df.columns):
                        max_length = max(
                            df[col_name].astype(str).map(len).max(),
                            len(str(col_name))
                        ) + 2
                        worksheet.set_column(col_num, col_num, max_length)
                
                output.seek(0)
                
                headers = {
                    'Content-Disposition': f'attachment; filename=attendance_{emp_id_int}_{year}_{month:02d}.xlsx'
                }
                print(f"[LOG] /reports/attendance returning Excel file for emp {emp_id_int} with {len(excel_data)} records")
                return Response(
                    content=output.read(), 
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                    headers=headers
                )
            except Exception as e:
                print(f"[ERROR] /reports/attendance Excel generation failed: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to generate Excel report")
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'json' or 'excel'")
    except HTTPException:
        raise
    except ValueError as e:
        print(f"[ERROR] /reports/attendance invalid parameters: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid parameters")
    except Exception as e:
        print(f"[ERROR] /reports/attendance exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
