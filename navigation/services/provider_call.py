import logging

import polyline as polyline_codec
import requests
from . import converter
from .helper import compute_cumulative_distances
from django.conf import settings

logger = logging.getLogger(__name__)


def get_route(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> dict:
    config = settings.FUEL_OPTIMIZER
    base_url = config["OSRM_BASE_URL"]
    logger.debug("Calling OSRM API with URL: %s", base_url)
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
    points = polyline_codec.decode(encoded_polyline)
    cumulative_distances = compute_cumulative_distances(points)

    return {
        "encoded_polyline": encoded_polyline,
        "points": points,
        "cumulative_distances": cumulative_distances,
        "total_distance_miles": total_distance_miles,
    }


def get_route_with_waypoints(
    waypoints: list[tuple[float, float]],
) -> dict:
    """
    Second OSRM call — route through an ordered list of waypoints.

    Parameters
    ----------
    waypoints :
        Ordered list of (lat, lng) tuples:
        [start, stop1, stop2, …, end].

    Returns
    -------
    dict
        ``route_polyline``       – encoded polyline of the full waypoint route
        ``total_distance_miles`` – real driving distance in miles
    """
    config = settings.FUEL_OPTIMIZER
    base_url = config["OSRM_BASE_URL"]

    coords = ";".join(f"{lng},{lat}" for lat, lng in waypoints)
    url = f"{base_url}/{coords}"
    params = {
        "overview": "full",
        "geometries": "polyline",
    }

    logger.debug("OSRM waypoint call: %s", url)
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        raise ValueError(
            f"OSRM waypoint routing failed: {data.get('code', 'unknown')}"
        )

    route = data["routes"][0]
    return {
        "route_polyline": route["geometry"],
        "total_distance_miles": converter.meters_to_miles(route["distance"]),
    }
