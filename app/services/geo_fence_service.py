from geopy.distance import geodesic

def is_within_geofence(user_lat: float, user_lon: float, office_lat: float, office_lon: float, radius_meters: int) -> bool:
    """
    Checks if a user's location is within a specified radius of an office location.

    This function uses the geopy library to calculate the geodesic distance, which is
    a highly accurate method for determining the distance between two points on
    the Earth's surface.

    Args:
        user_lat: Latitude of the user's current location.
        user_lon: Longitude of the user's current location.
        office_lat: Latitude of the target office location.
        office_lon: Longitude of the target office location.
        radius_meters: The radius of the geofence in meters.

    Returns:
        True if the user is within the geofence, False otherwise.
    """
    try:
        user_lat = round(user_lat, 7)
        user_lon = round(user_lon, 7)
        office_lat = round(office_lat, 7)
        office_lon = round(office_lon, 7)
        
        user_location = (user_lat, user_lon)
        office_location = (office_lat, office_lon)
        print(f"[GEO_LOG] User Location: {user_location}, Office Location: {office_location}, Radius: {radius_meters} meters")

        # Calculate the distance between the two points in meters
        distance = geodesic(user_location, office_location).meters

        print(f"[GEO_LOG] User is {distance:.2f} meters away from the office.")

        return distance <= radius_meters
    except ValueError as e:
        print(f"[GEO_ERROR] Invalid latitude or longitude value: {e}")
        return False

# new helper function for distance showing
def calculate_distance_meters(user_lat: float, user_lon: float, office_lat: float, office_lon: float) -> float:
    """
    Returns the geodesic distance between user and office in meters.
    This helper is used when you also want to show how far user is.
    """
    try:
        user_location = (float(user_lat), float(user_lon))
        office_location = (float(office_lat), float(office_lon))
        distance = geodesic(user_location, office_location).meters
        print(f"[GEO_LOG] Calculated distance: {distance:.2f} meters")
        return distance
    except Exception as e:
        print(f"[GEO_ERROR] calculate_distance_meters exception: {e}")
        return float("inf")

### How to Use This