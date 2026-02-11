import time
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from django.conf import settings


geolocator = Nominatim(
    user_agent=settings.NOMINATIM_USER_AGENT,
    timeout=10,
)

geolocator = Nominatim(
    user_agent="gasstation_django (bouroumanamoundher@gmail.com)"
)




def geocode(location_string: str) -> tuple[float, float]:
    """
    Geocode a US location string to (latitude, longitude)
    using Nominatim agent (geopy).
    """
    location = geolocator.geocode(location_string)
    if not location:
        raise ValueError(f"Could not geocode location: '{location_string}'")
    return location.latitude, location.longitude
