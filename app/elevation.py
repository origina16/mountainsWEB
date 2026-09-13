import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger(__name__)

ELEVATION_API = "https://api.open-meteo.com/v1/elevation"


def get_elevation_batch(points):
    """Get elevation for a list of points using Open-Meteo API.
    Each point: {lat, lng}
    Returns: list of elevation values (meters)
    """
    if not points:
        return []

    lats = [str(p["lat"]) for p in points]
    lngs = [str(p["lng"]) for p in points]

    params = urllib.parse.urlencode({
        "latitude": ",".join(lats),
        "longitude": ",".join(lngs),
    })

    url = f"{ELEVATION_API}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MountainRoutes/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("elevation", [0] * len(points))
    except Exception as e:
        logger.warning(f"Elevation API error: {e}")
        return [0] * len(points)


def enrich_points_with_elevation(points):
    """Add alt field to each point by fetching elevation from API.
    Each point: {lat, lng} -> {lat, lng, alt}
    """
    elevations = get_elevation_batch(points)
    result = []
    for i, p in enumerate(points):
        enriched = dict(p)
        enriched["alt"] = elevations[i] if i < len(elevations) else 0
        result.append(enriched)
    return result
