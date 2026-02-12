import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance **in miles** between two points."""
    R = 3958.8  
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
def project_point_onto_segment(
    p_lat: float, p_lng: float,
    a_lat: float, a_lng: float,
    b_lat: float, b_lng: float,
) -> tuple[float, float, float]:
    """
    Project point P onto the line segment A→B.

    Uses a locally-scaled flat-earth approximation where longitude is
    multiplied by cos(mid_latitude) to correct for meridian convergence.

    Parameters
    ----------
    p_lat, p_lng : station coordinates
    a_lat, a_lng : segment start (route point A)
    b_lat, b_lng : segment end   (route point B)

    Returns
    -------
    (t, proj_lat, proj_lng)
        t ∈ [0, 1]  – fraction along segment A→B where the projection falls
        proj_lat, proj_lng – coordinates of the projected point on the segment
    """
    mid_lat = math.radians((a_lat + b_lat) / 2)
    cos_lat = math.cos(mid_lat)

    dx = (b_lng - a_lng) * cos_lat
    dy = b_lat - a_lat

    if dx == 0 and dy == 0:
        return 0.0, a_lat, a_lng

    px = (p_lng - a_lng) * cos_lat
    py = p_lat - a_lat

    t = (px * dx + py * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    proj_lat = a_lat + t * (b_lat - a_lat)
    proj_lng = a_lng + t * (b_lng - a_lng)

    return t, proj_lat, proj_lng


def compute_cumulative_distances(points: list[tuple[float, float]]) -> list[float]:
    """
    Given decoded polyline points [(lat, lng), …], return a list of
    cumulative distances **in miles** from the first point.
    """
    distances = [0.0]
    for i in range(1, len(points)):
        d = haversine(
            points[i - 1][0], points[i - 1][1],
            points[i][0], points[i][1],
        )
        distances.append(distances[-1] + d)
    return distances
