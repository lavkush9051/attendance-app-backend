from typing import List, Optional, Dict, Any
from app.repositories.geofence_repo import GeofenceRepository
from app.models import GeofenceLocation
from app.services.geo_fence_service import calculate_distance_meters

class GeofenceService:
    """Service for geofence validation logic"""
    
    def __init__(self, geofence_repo: GeofenceRepository):
        self.geofence_repo = geofence_repo
    
    def validate_employee_location(
        self, 
        emp_id: int, 
        user_lat: float, 
        user_lon: float
    ) -> Dict[str, Any]:
        """
        Validate if employee is within their permitted geofence locations
        
        Returns:
            {
                "is_valid": bool,
                "message": str,
                "distance": float (optional),
                "nearest_block": str (optional)
            }
        """
        # Check if employee has any geofence access
        if not self.geofence_repo.has_geofence_access(emp_id):
            return {
                "is_valid": False,
                "message": "Access not permitted. Please contact your administrator to grant geofence access.",
                "code": "NO_ACCESS"
            }
        
        # Get all permitted geofence locations for this employee
        permitted_locations = self.geofence_repo.get_employee_geofence_access(emp_id)
        
        if not permitted_locations:
            return {
                "is_valid": False,
                "message": "No geofence locations found for your access.",
                "code": "NO_LOCATIONS"
            }
        
        # Check if user is within any of the permitted locations
        closest_location = None
        closest_distance = float('inf')
        
        for location in permitted_locations:
            distance = calculate_distance_meters(
                user_lat, 
                user_lon, 
                float(location.lat), 
                float(location.lon)
            )
            
            # If within radius, access granted
            if distance <= location.radius:
                return {
                    "is_valid": True,
                    "message": f"Access granted at {location.block}",
                    "distance": round(distance, 2),
                    "block": location.block,
                    "code": "ACCESS_GRANTED"
                }
            
            # Track closest location for error message
            if distance < closest_distance:
                closest_distance = distance
                closest_location = location
        
        # User not within any permitted location
        if closest_location:
            return {
                "is_valid": False,
                "message": f"You are not within the permissible area. You are {closest_distance:.2f} meters away from {closest_location.block} (allowed radius: {closest_location.radius} meters).",
                "distance": round(closest_distance, 2),
                "nearest_block": closest_location.block,
                "allowed_radius": closest_location.radius,
                "code": "OUT_OF_RANGE"
            }
        
        return {
            "is_valid": False,
            "message": "Unable to validate location.",
            "code": "VALIDATION_ERROR"
        }
