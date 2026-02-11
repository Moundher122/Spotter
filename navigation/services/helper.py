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