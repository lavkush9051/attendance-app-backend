# app/main.py
# Updated repository fix applied
import asyncio
from fastapi import FastAPI, Request, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.auth_routes import router as auth_router
from app.api.routes import clock, attendance, employees, leaves, faces, reports
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for JWT authentication logging and error handling
    """
    
    async def dispatch(self, request: Request, call_next):
        # Log all requests for debugging
        logger.info(f"Request: {request.method} {request.url}")
        
        # Check if Authorization header is present for protected routes
        if request.url.path.startswith("/api/") and request.method != "OPTIONS":
            auth_header = request.headers.get("Authorization")
            if auth_header:
                logger.info(f"Auth header present: {auth_header[:20]}...")
            else:
                logger.info("No auth header found")
        
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            logger.error(f"HTTP Exception: {e.status_code} - {e.detail}")
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

app = FastAPI(
    title="Attendance & Leave Management API",
    description="FastAPI backend for face recognition based attendance system",
    version="1.0.0"
)

# Add custom auth middleware
app.add_middleware(AuthMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:3000/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure this for production
)

# Initialize SAP sync service on startup
@app.on_event("startup")
async def start_sap_sync():
    from app.repositories.attendance_repo import AttendanceRepository
    from app.repositories.employee_repo import EmployeeRepository
    from app.services.attendance_service import AttendanceService
    from app.services.employee_service import EmployeeService
    from app.services.sap_sync_service import SAPSyncService
    from app.repositories.clock_repo import ClockRepository
    from app.database import SessionLocal

    # Create a database session for startup tasks and repositories
    db = SessionLocal()
    # Attach to app.state so it can be closed on shutdown
    app.state.db = db

    # Initialize repositories and services with the DB session
    employee_repo = EmployeeRepository(db)
    attendance_repo = AttendanceRepository(db)
    clock_repo = ClockRepository(db)
    attendance_service = AttendanceService(attendance_repo, employee_repo, clock_repo)
    employee_service = EmployeeService(employee_repo)

    # Initialize SAP sync service and start scheduler
    sap_sync_service = SAPSyncService(attendance_service, employee_service)
    # store for endpoint access
    app.state.sap_sync_service = sap_sync_service
    # Log current SAP configuration for visibility
    try:
        from app.core.config import settings
        logger.info(
            f"SAP config -> ENV: {settings.SAP_ENV}, BASE_URL: {settings.SAP_BASE_URL}, "
            f"CLIENT: {settings.SAP_CLIENT}, SEND_VIA: {settings.SAP_SEND_VIA}"
        )
    except Exception as e:
        logger.warning(f"Unable to log SAP config: {e}")
    # Start both attendance and leave schedulers
    asyncio.create_task(sap_sync_service.schedule_shift_sync())
    asyncio.create_task(sap_sync_service.schedule_leave_sync())
    logger.info("Started SAP sync schedulers (attendance + leave)")

    # Initialize and start leave auto-cancel service
    from app.services.leave_auto_cancel_service import LeaveAutoCancelService
    leave_auto_cancel_service = LeaveAutoCancelService()
    app.state.leave_auto_cancel_service = leave_auto_cancel_service
    asyncio.create_task(leave_auto_cancel_service.schedule_auto_cancel())
    logger.info("Started leave auto-cancel scheduler")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    db = getattr(app.state, "db", None)
    if db:
        try:
            db.close()
            logger.info("Database session closed on shutdown")
        except Exception as e:
            logger.error(f"Error closing DB on shutdown: {e}")

# Include auth routes (existing)
app.include_router(auth_router)

# Health check endpoint for Docker
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    return {"status": "healthy", "message": "AmeTech HRMS API is running"}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AmeTech HRMS API",
        "version": "1.0.0",
        "status": "running",
        "health_check": "/health"
    }

# Include modular API routes
app.include_router(clock.router, prefix="/api", tags=["clock"])
app.include_router(attendance.router, prefix="/api", tags=["attendance"])  
app.include_router(employees.router, prefix="/api", tags=["employees"])
app.include_router(leaves.router, prefix="/api", tags=["leaves"])
app.include_router(faces.router, prefix="/api", tags=["faces"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])

# Quick SAP config inspection endpoint (no secrets)
@app.get("/sap-config")
async def get_sap_config():
    from app.core.config import settings
    return {
        "env": settings.SAP_ENV,
        "base_url": settings.SAP_BASE_URL,
        "client": settings.SAP_CLIENT,
        "send_via": settings.SAP_SEND_VIA,
    }

# Hardcoded one-time SAP sync trigger endpoint (testing only)
@app.post("/sap-sync/hardcoded")
async def trigger_hardcoded_sap_sync(date: str = Query(None, description="Date in YYYY-MM-DD format; defaults to today if omitted")):
    from datetime import datetime
    from app.services.sap_sync_hardcoded import run_test_sync
    sap_service = getattr(app.state, "sap_sync_service", None)
    if not sap_service:
        raise HTTPException(status_code=500, detail="SAP sync service not initialized")
    target_date = date or datetime.utcnow().strftime("%Y-%m-%d")
    summary = await run_test_sync(sap_service, target_date)
    return {"status": "completed", **summary}

# Manual leave sync endpoint
@app.post("/sap-sync/leaves")
async def trigger_leave_sap_sync(date: str = Query(None, description="Date in YYYY-MM-DD format; defaults to today if omitted")):
    from datetime import datetime
    sap_service = getattr(app.state, "sap_sync_service", None)
    if not sap_service:
        raise HTTPException(status_code=500, detail="SAP sync service not initialized")
    target_date_str = date or datetime.utcnow().strftime("%Y-%m-%d")
    target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    summary = await sap_service.sync_leaves_for_date(target_dt)
    return {"status": "completed", **summary}

# Manual leave auto-cancel endpoint
@app.post("/leave-auto-cancel")
async def trigger_leave_auto_cancel(date: str = Query(None, description="Date in YYYY-MM-DD format; defaults to today if omitted")):
    from datetime import datetime
    auto_cancel_service = getattr(app.state, "leave_auto_cancel_service", None)
    if not auto_cancel_service:
        raise HTTPException(status_code=500, detail="Leave auto-cancel service not initialized")
    target_date_str = date or datetime.utcnow().strftime("%Y-%m-%d")
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    summary = await auto_cancel_service.auto_cancel_pending_leaves(target_date)
    return {"status": "completed", **summary}