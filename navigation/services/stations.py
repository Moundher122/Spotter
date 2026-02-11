"""
Station projection service — find gas stations near the route, project them
onto the route polyline, and return a sorted list with ``distance_from_start``.

Uses the GasStation model's PointField (PostGIS geometry) directly.
No external API calls are made.
"""

import logging

from django.conf import settings
from django.contrib.gis.geos import Polygon

from gasstation.models import GasStation
from .helper import haversine

logger = logging.getLogger(__name__)


def get_stations_along_route(
    route_points: list[tuple[float, float]],
    cumulative_distances: list[float],
    max_station_distance: float | None = None,
    max_range: float | None = None,
) -> list[dict]:
    """
    Project gas stations from the database onto the route.

    Only stations that the truck can actually reach from the start
    (i.e. ``distance_from_start <= max_range``) are kept.

    Algorithm:
      1. Compute a bounding box around the route polyline.
      2. Expand it slightly to capture nearby stations.
      3. Query the DB for stations within the bounding box.
      4. For each station, find its closest route point and assign
         ``distance_from_start``.
      5. Remove stations that are too far from the route.
      6. Remove stations beyond the truck's max range from start.
      7. Sort by ``distance_from_start``.

    Parameters
    ----------
    route_points :
        Decoded polyline as [(lat, lng), …].
    cumulative_distances :
        Cumulative driving distance (miles) for each polyline point.
    max_station_distance :
        Maximum perpendicular distance (miles) from the route to keep
        a station.  Default from settings.
    max_range :
        Maximum range of the truck in miles (default from settings).
        Stations beyond this distance from start are discarded.

    Returns
    -------
    list[dict]
        Sorted list of station dicts with keys:
        ``id``, ``name``, ``lat``, ``lng``, ``price``,
        ``distance_from_start``, ``distance_from_route``.
    """
    config = settings.FUEL_OPTIMIZER
    if max_station_distance is None:
        max_station_distance = config["MAX_STATION_DISTANCE_FROM_ROUTE_MILES"]
    if max_range is None:
        max_range = config["MAX_RANGE_MILES"]

    # ------------------------------------------------------------------
    # Step 1-2: Bounding box with padding
    # ------------------------------------------------------------------
    lats = [p[0] for p in route_points]
    lngs = [p[1] for p in route_points]
    padding = 0.5  # ≈ 35 miles
    min_lat, max_lat = min(lats) - padding, max(lats) + padding
    min_lng, max_lng = min(lngs) - padding, max(lngs) + padding

    # ------------------------------------------------------------------
    # Step 3: Query stations within bounding box using PostGIS
    # ------------------------------------------------------------------
    bbox = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
    bbox.srid = 4326

    stations_qs = GasStation.objects.filter(location__within=bbox)
    bbox_count = stations_qs.count()
    logger.info("Stations within bounding box: %d", bbox_count)

    # ------------------------------------------------------------------
    # Sub-sample route points for faster nearest-point search
    # ------------------------------------------------------------------
    total_points = len(route_points)
    step = max(1, total_points // 2000)
    sampled_indices = list(range(0, total_points, step))
    if sampled_indices[-1] != total_points - 1:
        sampled_indices.append(total_points - 1)

    sampled = [
        (route_points[i][0], route_points[i][1], cumulative_distances[i])
        for i in sampled_indices
    ]
    logger.debug("Using %d sampled route points for projection", len(sampled))

    # ------------------------------------------------------------------
    # Step 4: Project each station onto route
    # ------------------------------------------------------------------
    projected: list[dict] = []

    for station in stations_qs.iterator():
        # Extract lat/lng from the PointField
        station_lat = station.location.y
        station_lng = station.location.x

        best_dist = float("inf")
        best_cum = 0.0

        for pt_lat, pt_lng, cum_dist in sampled:
            # Quick rectangular pre-filter (≈0.4° ≈ 28 mi)
            if (
                abs(pt_lat - station_lat) > 0.4
                or abs(pt_lng - station_lng) > 0.5
            ):
                continue
            d = haversine(station_lat, station_lng, pt_lat, pt_lng)
            if d < best_dist:
                best_dist = d
                best_cum = cum_dist

        # Step 5: Keep only stations close enough to the route
        # Step 6: Keep only stations the truck can reach from start
        if best_dist <= max_station_distance and best_cum <= max_range:
            projected.append(
                {
                    "id": station.opis_id,
                    "name": station.name,
                    "lat": station_lat,
                    "lng": station_lng,
                    "price": float(station.retail_price),
                    "distance_from_start": best_cum,
                    "distance_from_route": round(best_dist, 2),
                }
            )

    # ------------------------------------------------------------------
    # Step 6: Sort by distance_from_start
    # ------------------------------------------------------------------
    projected.sort(key=lambda s: s["distance_from_start"])

    logger.info("Stations projected onto route: %d", len(projected))
    return projected
