import logging

logger = logging.getLogger(__name__)

DUMMY_LOCATIONS = {
    "tomah_exit_143": (43.9786, -90.5040),
    "chicago_il":     (41.8781, -87.6298),
}

DEFAULT_START = (46.8772, -96.7898)
DEFAULT_END   = (41.8781, -87.6298)

_call_count = 0

def geocode(location_string: str) -> tuple[float, float]:
    global _call_count
    _call_count += 1

    location_lower = location_string.lower()
    for key, coords in DUMMY_LOCATIONS.items():
        if key in location_lower:
            logger.debug("Dummy geocode '%s' -> %s", location_string, coords)
            return coords

    fallback = DEFAULT_START if _call_count % 2 == 1 else DEFAULT_END
    logger.debug("Dummy geocode (fallback) '%s' -> %s", location_string, fallback)
    return fallback
