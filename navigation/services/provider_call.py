import polyline as polyline_codec
import requests
from . import converter
from .helper import compute_cumulative_distances
from django.conf import settings

def get_route(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> dict:
    """
    Call the OSRM routing API **once** and return:

    - ``encoded_polyline``   – the raw encoded polyline string
    - ``points``             – decoded list of (lat, lng) tuples
    - ``cumulative_distances`` – miles from start for every polyline point
    - ``total_distance_miles`` – total driving distance in miles
    """
    config = settings.FUEL_OPTIMIZER
    base_url = config["OSRM_BASE_URL"]
    print(f"Calling OSRM API with URL: {base_url}")
    url = f"{base_url}/{start_lng},{start_lat};{end_lng},{end_lat}"
    params = {
        "overview": "full",
        "geometries": "polyline",
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    
    if data.get("code") != "Ok":
        raise ValueError(
            f"OSRM routing failed with code: {data.get('code', 'unknown')}"
        )
    route = data["routes"][0]
    encoded_polyline = route["geometry"]
    total_distance_miles = converter.meters_to_miles(route["distance"])
    # Decode polyline → list of (lat, lng)
    points = polyline_codec.decode(encoded_polyline)

    # Cumulative distance from start for every point
    cumulative_distances = compute_cumulative_distances(points)

    return {
        "encoded_polyline": encoded_polyline,
        "points": points,
        "cumulative_distances": cumulative_distances,
        "total_distance_miles": total_distance_miles,
    }
