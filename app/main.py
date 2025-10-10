# app/main.py
# Updated repository fix applied
from fastapi import FastAPI, Request, HTTPException, status
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

# Include auth routes (existing)
app.include_router(auth_router)

# Include modular API routes
app.include_router(clock.router, prefix="/api", tags=["clock"])
app.include_router(attendance.router, prefix="/api", tags=["attendance"])  
app.include_router(employees.router, prefix="/api", tags=["employees"])
app.include_router(leaves.router, prefix="/api", tags=["leaves"])
app.include_router(faces.router, prefix="/api", tags=["faces"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])