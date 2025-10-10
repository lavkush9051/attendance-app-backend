@echo off
echo Starting FastAPI Server...
cd /d "C:\Users\ameis\Desktop\Attendance_leave_management\face-recognition-service"
call .venv\Scripts\activate.bat
echo Virtual environment activated
echo Starting uvicorn server on http://127.0.0.1:8000
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause