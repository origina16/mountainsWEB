import math

EARTH_RADIUS_KM = 6371.0


def haversine(lat1, lon1, lat2, lon2):
    """2D distance between two points on Earth (km)."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def haversine_3d(lat1, lon1, alt1, lat2, lon2, alt2):
    """3D distance between two points considering elevation (km).
    alt1, alt2 in meters.
    """
    horizontal = haversine(lat1, lon1, lat2, lon2)
    vertical = (alt2 - alt1) / 1000.0
    return math.sqrt(horizontal ** 2 + vertical ** 2)


def bearing(lat1, lon1, lat2, lon2):
    """Initial bearing (azimuth) from point 1 to point 2 in degrees."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bearing_name(deg):
    """Convert bearing degrees to compass direction."""
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return directions[round(deg / 45) % 8]


def calculate_route_distance(points):
    """Total distance of a route with elevation (km).
    Each point: {lat, lng, alt} where alt is meters.
    """
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i + 1]
        alt1 = p1.get("alt", 0) or 0
        alt2 = p2.get("alt", 0) or 0
        total += haversine_3d(p1["lat"], p1["lng"], alt1, p2["lat"], p2["lng"], alt2)
    return total


def get_elevation_gain(points):
    """Total elevation gain (meters) along the route."""
    gain = 0.0
    for i in range(1, len(points)):
        prev = points[i - 1].get("alt", 0) or 0
        curr = points[i].get("alt", 0) or 0
        if curr > prev:
            gain += curr - prev
    return gain


def get_elevation_loss(points):
    """Total elevation loss (meters) along the route."""
    loss = 0.0
    for i in range(1, len(points)):
        prev = points[i - 1].get("alt", 0) or 0
        curr = points[i].get("alt", 0) or 0
        if curr < prev:
            loss += prev - curr
    return loss


def get_route_stats(points):
    """Full statistics for a route."""
    if len(points) < 2:
        return {
            "total_distance_km": 0.0,
            "total_elevation_gain_m": 0,
            "total_elevation_loss_m": 0,
            "max_altitude_m": 0,
            "min_altitude_m": 0,
            "start": None,
            "end": None,
        }

    alts = [p.get("alt", 0) or 0 for p in points]
    return {
        "total_distance_km": round(calculate_route_distance(points), 3),
        "total_elevation_gain_m": round(get_elevation_gain(points)),
        "total_elevation_loss_m": round(get_elevation_loss(points)),
        "max_altitude_m": round(max(alts)),
        "min_altitude_m": round(min(alts)),
        "start": {"lat": points[0]["lat"], "lng": points[0]["lng"], "alt": alts[0]},
        "end": {"lat": points[-1]["lat"], "lng": points[-1]["lng"], "alt": alts[-1]},
    }
