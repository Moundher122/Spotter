"""Map renderer — draw the route polyline and fuel stops on an OpenStreetMap
static image, save it to Django media storage, and return the relative path.

Uses the ``staticmap`` library which fetches OSM tiles and composites
them locally.  No API key required.
"""

import io
import logging
import uuid

import polyline as polyline_codec
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from staticmap import StaticMap, Line, CircleMarker

logger = logging.getLogger(__name__)

# Map dimensions (pixels)
MAP_WIDTH = 800
MAP_HEIGHT = 500

# Sub-directory inside MEDIA_ROOT
MAP_UPLOAD_DIR = "route_maps"


def render_route_map(
    encoded_polyline: str,
    fuel_stops: list[dict] | None = None,
) -> str:
    """
    Render the route polyline (and optional fuel-stop markers) onto a
    static OSM map, save it to media storage, and return the relative
    file path (e.g. ``route_maps/abc123.png``).

    Parameters
    ----------
    encoded_polyline :
        Google-encoded polyline string.
    fuel_stops :
        Optional list of stop dicts, each with ``lat`` and ``lng`` keys.

    Returns
    -------
    str
        Relative path inside MEDIA_ROOT.
    """
    # Decode polyline
    points = polyline_codec.decode(encoded_polyline)

    m = StaticMap(
        MAP_WIDTH, MAP_HEIGHT,
        url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    )

    route_coords = [(lng, lat) for lat, lng in points]
    m.add_line(Line(route_coords, color="blue", width=3))

    if route_coords:
        m.add_marker(CircleMarker(route_coords[0], color="green", width=12))
        m.add_marker(CircleMarker(route_coords[-1], color="red", width=12))

    if fuel_stops:
        for stop in fuel_stops:
            coord = (stop["lng"], stop["lat"])
            m.add_marker(CircleMarker(coord, color="orange", width=8))

    image = m.render()

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)

    filename = f"{MAP_UPLOAD_DIR}/{uuid.uuid4().hex}.png"
    saved_path = default_storage.save(filename, ContentFile(buf.read()))

    logger.debug("Saved route map: %s", saved_path)
    return saved_path
