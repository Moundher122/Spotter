import time

import requests
from django.conf import settings



def geocode(location_string: str) -> tuple[float, float]:
    """
    Geocode a US location string to (latitude, longitude) using
    the OpenStreetMap Nominatim API.
    Raises ValueError if the location cannot be resolved.
    """
    config = settings.FUEL_OPTIMIZER
    params = {
        "q": location_string,
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
    }
    headers = {
        "User-Agent": config["NOMINATIM_USER_AGENT"],
    }
    response = requests.get(
        config["NOMINATIM_URL"],
        params=params,
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise ValueError(f"Could not geocode location: '{location_string}'")
    lat = float(results[0]["lat"])
    lng = float(results[0]["lon"])
    time.sleep(1.1)
    return lat, lng
