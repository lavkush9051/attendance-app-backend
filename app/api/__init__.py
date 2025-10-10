from fastapi import APIRouter
from .routes import auth, clock, attendance, employees, leaves, faces, reports

router = APIRouter()

# Include all route modules
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(clock.router, prefix="", tags=["clock"])  # Keep existing paths
router.include_router(attendance.router, prefix="", tags=["attendance"])
router.include_router(employees.router, prefix="", tags=["employees"])
router.include_router(leaves.router, prefix="", tags=["leaves"])  
router.include_router(faces.router, prefix="", tags=["faces"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])