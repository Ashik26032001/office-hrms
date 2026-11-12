"""
Geofencing service.
Reads office location from CompanySettings (DB) first.
Falls back to settings.py if DB not available.
"""
import math


def get_office_config():
    """Return office lat, lon, radius from DB settings."""
    try:
        from dashboard.models import CompanySettings
        cfg = CompanySettings.get()
        return cfg.office_latitude, cfg.office_longitude, cfg.geofence_radius, cfg.geofence_enabled
    except Exception:
        from django.conf import settings
        lat    = getattr(settings, 'OFFICE_LATITUDE',  10.0261)
        lon    = getattr(settings, 'OFFICE_LONGITUDE', 76.3083)
        radius = getattr(settings, 'OFFICE_GEOFENCE_RADIUS_METRES', 200)
        return lat, lon, radius, True


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1   = math.radians(lat1)
    phi2   = math.radians(lat2)
    d_phi  = math.radians(lat2 - lat1)
    d_lam  = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2)
    return 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def check_geofence(latitude, longitude):
    """
    Check if coordinates are within the office geofence.
    Returns dict: is_valid, distance, radius, office_lat, office_lon, message
    """
    office_lat, office_lon, radius, enabled = get_office_config()

    # If geofencing is disabled in settings — always pass
    if not enabled:
        return {
            'is_valid':   True,
            'distance':   0,
            'radius':     radius,
            'office_lat': office_lat,
            'office_lon': office_lon,
            'message':    'Geofencing is disabled — location not checked.',
        }

    distance = haversine_distance(latitude, longitude, office_lat, office_lon)
    is_valid  = distance <= radius

    if is_valid:
        message = f"Location verified. You are {int(distance)}m from office."
    else:
        message = (
            f"Location check failed. You are {int(distance)}m away. "
            f"Must be within {radius}m of the office."
        )

    return {
        'is_valid':   is_valid,
        'distance':   round(distance, 1),
        'radius':     radius,
        'office_lat': office_lat,
        'office_lon': office_lon,
        'message':    message,
    }
