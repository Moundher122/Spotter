import logging
import time

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError
from django.conf import settings

logger = logging.getLogger(__name__)

geolocator = Nominatim(
    user_agent=settings.NOMINATIM_USER_AGENT,
    timeout=10,
)

MAX_RETRIES = 3
RETRY_DELAY = 2 


def geocode(location_string: str) -> tuple[float, float]:
    """
    Geocode a US location string to (latitude, longitude)
    using Nominatim agent (geopy).

    Retries up to MAX_RETRIES times with exponential backoff
    when Nominatim rate-limits (HTTP 509 / 429).
    """
    logger.debug("Geocoding: %s", location_string)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            location = geolocator.geocode(location_string)
            if not location:
                raise ValueError(f"Could not geocode location: '{location_string}'")
            logger.debug(
                "Geocoded '%s' -> (%s, %s)",
                location_string, location.latitude, location.longitude,
            )
            return location.latitude, location.longitude
        except GeocoderServiceError as e:
            last_error = e
            delay = RETRY_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Nominatim rate-limited (attempt %d/%d): %s — retrying in %ds",
                attempt, MAX_RETRIES, e, delay,
            )
            time.sleep(delay)

    raise RuntimeError(
        f"Nominatim still rate-limiting after {MAX_RETRIES} retries: {last_error}"
    )
