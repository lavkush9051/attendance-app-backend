from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import GeofenceLocation, EmployeeGeofenceAccess

class GeofenceRepository:
    """Repository for geofence operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_employee_geofence_access(self, emp_id: int) -> List[GeofenceLocation]:
        """Get all geofence locations that an employee has access to"""
        result = self.db.query(GeofenceLocation).join(
            EmployeeGeofenceAccess,
            GeofenceLocation.id == EmployeeGeofenceAccess.ega_geofence_id
        ).filter(
            EmployeeGeofenceAccess.ega_emp_id == emp_id
        ).all()
        
        return result
    
    def has_geofence_access(self, emp_id: int) -> bool:
        """Check if employee has any geofence access"""
        count = self.db.query(EmployeeGeofenceAccess).filter(
            EmployeeGeofenceAccess.ega_emp_id == emp_id
        ).count()
        
        return count > 0
    
    def get_geofence_by_id(self, geofence_id: int) -> Optional[GeofenceLocation]:
        """Get a specific geofence location by ID"""
        return self.db.query(GeofenceLocation).filter(
            GeofenceLocation.id == geofence_id
        ).first()
    
    def get_all_geofence_locations(self) -> List[GeofenceLocation]:
        """Get all geofence locations"""
        return self.db.query(GeofenceLocation).all()
