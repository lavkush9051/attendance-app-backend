@echo off
echo Running API Tests...
cd /d "C:\Users\ameis\Desktop\Attendance_leave_management\face-recognition-service"
call .venv\Scripts\activate.bat
echo Virtual environment activated
echo Testing API endpoints...
python test_api.py
echo.
echo Tests completed!
pause