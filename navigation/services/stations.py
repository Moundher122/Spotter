import logging

from django.conf import settings
from django.contrib.gis.geos import Polygon

from gasstation.models import GasStation
from .helper import haversine, project_point_onto_segment

logger = logging.getLogger(__name__)


def get_stations_along_route(
    route_points: list[tuple[float, float]],
    cumulative_distances: list[float],
    max_station_distance: float | None = None,
) -> list[dict]:
    """
    Project gas stations from the database onto the route.

    All stations close enough to the route are kept regardless of
    distance from start.  The DP optimizer enforces the tank-range
    constraint (consecutive stops ≤ 500 mi apart).

    Algorithm:
      1. Compute a bounding box around the route polyline.
      2. Expand it slightly to capture nearby stations.
      3. Query the DB for stations within the bounding box.
      4. For each station, find its closest route point and assign
         ``distance_from_start``.
      5. Remove stations that are too far from the route.
      6. Sort by ``distance_from_start``.

    Parameters
    ----------
    route_points :
        Decoded polyline as [(lat, lng), …].
    cumulative_distances :
        Cumulative driving distance (miles) for each polyline point.
    max_station_distance :
        Maximum perpendicular distance (miles) from the route to keep
        a station.  Default from settings.

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
    lats = [p[0] for p in route_points]
    lngs = [p[1] for p in route_points]
    padding = 0.5 
    min_lat, max_lat = min(lats) - padding, max(lats) + padding
    min_lng, max_lng = min(lngs) - padding, max(lngs) + padding
    bbox = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
    bbox.srid = 4326

    stations_qs = GasStation.objects.filter(location__within=bbox)
    bbox_count = stations_qs.count()
    logger.info("Stations within bounding box: %d", bbox_count)
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

    projected: list[dict] = []

    for station in stations_qs.iterator():
        station_lat = station.location.y
        station_lng = station.location.x

        best_dist = float("inf")
        best_cum = 0.0

        for pt_lat, pt_lng, cum_dist in sampled:
            if (
                abs(pt_lat - station_lat) > 0.4
                or abs(pt_lng - station_lng) > 0.5
            ):
                continue
            d = haversine(station_lat, station_lng, pt_lat, pt_lng)
            if d < best_dist:
                best_dist = d
                best_cum = cum_dist

        if best_dist <= max_station_distance:
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
    projected.sort(key=lambda s: s["distance_from_start"])

    logger.info("Stations projected onto route: %d", len(projected))
    return projected

def get_stations_along_route_v2(
    route_points: list[tuple[float, float]],
    cumulative_distances: list[float],
    max_station_distance: float | None = None,
) -> list[dict]:
    """
    Project gas stations onto the route using **perpendicular segment
    projection** instead of nearest-point lookup.

    For every route segment A→B the station is projected onto the line,
    giving a parameter *t ∈ [0, 1]*.  The cumulative distance at the
    projection is interpolated as ``cum_A + t × (cum_B − cum_A)``.

    This yields a more accurate ``distance_from_start`` than v1's
    nearest-sampled-point approach, especially on curvy routes or when
    stations sit between two widely-spaced sample points.

    The rest of the pipeline (bounding-box query, sub-sampling, sorting)
    is identical to v1.
    """
    config = settings.FUEL_OPTIMIZER
    if max_station_distance is None:
        max_station_distance = config["MAX_STATION_DISTANCE_FROM_ROUTE_MILES"]

    lats = [p[0] for p in route_points]
    lngs = [p[1] for p in route_points]
    padding = 0.5
    min_lat, max_lat = min(lats) - padding, max(lats) + padding
    min_lng, max_lng = min(lngs) - padding, max(lngs) + padding

    bbox = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
    bbox.srid = 4326

    stations_qs = GasStation.objects.filter(location__within=bbox)
    bbox_count = stations_qs.count()
    logger.info("[v2] Stations within bounding box: %d", bbox_count)

    total_points = len(route_points)
    step = max(1, total_points // 2000)
    sampled_indices = list(range(0, total_points, step))
    if sampled_indices[-1] != total_points - 1:
        sampled_indices.append(total_points - 1)

    sampled = [
        (route_points[i][0], route_points[i][1], cumulative_distances[i])
        for i in sampled_indices
    ]
    logger.debug("[v2] Using %d sampled route points for projection", len(sampled))

    projected: list[dict] = []

    for station in stations_qs.iterator():
        station_lat = station.location.y
        station_lng = station.location.x

        best_dist = float("inf")
        best_cum = 0.0

        for k in range(len(sampled) - 1):
            a_lat, a_lng, a_cum = sampled[k]
            b_lat, b_lng, b_cum = sampled[k + 1]

            seg_min_lat = min(a_lat, b_lat) - 0.4
            seg_max_lat = max(a_lat, b_lat) + 0.4
            seg_min_lng = min(a_lng, b_lng) - 0.5
            seg_max_lng = max(a_lng, b_lng) + 0.5

            if not (
                seg_min_lat <= station_lat <= seg_max_lat
                and seg_min_lng <= station_lng <= seg_max_lng
            ):
                continue

            t, proj_lat, proj_lng = project_point_onto_segment(
                station_lat, station_lng,
                a_lat, a_lng,
                b_lat, b_lng,
            )

            d = haversine(station_lat, station_lng, proj_lat, proj_lng)

            if d < best_dist:
                best_dist = d
                best_cum = a_cum + t * (b_cum - a_cum)

        if best_dist <= max_station_distance:
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

    projected.sort(key=lambda s: s["distance_from_start"])
    logger.info("[v2] Stations projected onto route: %d", len(projected))
    return projected
