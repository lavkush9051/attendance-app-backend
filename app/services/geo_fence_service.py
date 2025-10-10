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
        user_lat = round(user_lat, 4)
        user_lon = round(user_lon, 4)
        office_lat = round(office_lat, 4)
        office_lon = round(office_lon, 4)
        
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


### How to Use This