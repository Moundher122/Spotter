"""
Forward Dynamic Programming optimizer for globally optimal fuel cost.

The route is fixed.  We optimise fuel purchase decisions only.
Stations are ordered by ``distance_from_start`` along the route.
The algorithm computes the globally minimal fuel cost to reach the destination.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def optimize_fuel_stops(
    stations: list[dict],
    total_distance: float,
    max_range: float | None = None,
    mpg: float | None = None,
) -> dict:
    """
    Forward dynamic programming over ordered nodes along a fixed route.

    Parameters
    ----------
    stations :
        Sorted list of station dicts, each with at least:
        ``id``, ``name``, ``lat``, ``lng``, ``price``, ``distance_from_start``.
    total_distance :
        Total driving distance of the route in miles.
    max_range :
        Vehicle max range (full tank) in miles.  Default from settings (500).
    mpg :
        Vehicle fuel efficiency in miles per gallon.  Default from settings (10).

    Returns
    -------
    dict
        ``fuel_stops``      – list of optimal stop dicts
        ``total_fuel_cost`` – globally minimal cost ($)
        ``total_distance``  – total route distance (miles)
        ``total_gallons``   – total fuel consumed (gallons)

    Raises
    ------
    ValueError
        If the destination is unreachable within the tank constraint.
    """
    config = settings.FUEL_OPTIMIZER
    if max_range is None:
        max_range = config["MAX_RANGE_MILES"]       # 500
    if mpg is None:
        mpg = config["MPG"]                         # 10

    # ──────────────────────────────────────────────────────────────────────
    # Short-route fast path:  if the truck can cover the entire distance
    # on a single tank, no fuel stop is needed → zero cost.
    # ──────────────────────────────────────────────────────────────────────
    if total_distance <= max_range:
        total_gallons = round(total_distance / mpg, 2)
        logger.info(
            "Route is %.1f miles (≤ %d max range) — no fuel stops needed.",
            total_distance,
            max_range,
        )
        return {
            "fuel_stops": [],
            "total_fuel_cost": 0.0,
            "total_distance": round(total_distance, 1),
            "total_gallons": total_gallons,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Build ordered node list:  Start  →  Stations  →  Destination
    # ──────────────────────────────────────────────────────────────────────
    nodes: list[dict] = []

    # Virtual start node (price = 0, no fuel purchase here)
    nodes.append(
        {
            "id": "start",
            "price": 0,
            "distance_from_start": 0.0,
            "is_virtual": True,
        }
    )

    # Real station nodes (already sorted by distance_from_start)
    for s in stations:
        nodes.append(
            {
                "id": s["id"],
                "name": s.get("name", ""),
                "lat": s.get("lat"),
                "lng": s.get("lng"),
                "price": s["price"],
                "distance_from_start": s["distance_from_start"],
                "is_virtual": False,
            }
        )

    # Virtual destination node
    nodes.append(
        {
            "id": "destination",
            "price": 0,
            "distance_from_start": total_distance,
            "is_virtual": True,
        }
    )

    n = len(nodes)
    logger.info("DP over %d nodes (start + %d stations + destination)", n, n - 2)

    # ──────────────────────────────────────────────────────────────────────
    # Forward DP
    #
    #   dp[i] = minimum fuel cost to reach node i
    #
    #   For each node i (in increasing distance order):
    #       For each node j reachable from i  (0 < gap ≤ max_range):
    #           fuel_needed = gap / mpg          (gallons)
    #           fuel_cost   = fuel_needed × price_at_node_i
    #           dp[j] = min(dp[j], dp[i] + fuel_cost)
    # ──────────────────────────────────────────────────────────────────────
    INF = float("inf")
    dp = [INF] * n
    parent = [-1] * n
    dp[0] = 0.0

    for i in range(n):
        if dp[i] == INF:
            continue                  
        for j in range(i + 1, n):
            gap = nodes[j]["distance_from_start"] - nodes[i]["distance_from_start"]

            if gap <= 0:
                continue
            if gap > max_range:
                break                 

            fuel_needed = gap / mpg
            fuel_cost = fuel_needed * nodes[i]["price"]
            candidate = dp[i] + fuel_cost

            if candidate < dp[j]:
                dp[j] = candidate
                parent[j] = i

    # ──────────────────────────────────────────────────────────────────────
    # Check feasibility
    # ──────────────────────────────────────────────────────────────────────
    dest_idx = n - 1
    if dp[dest_idx] == INF:
        raise ValueError(
            f"Destination is unreachable with the given tank constraint "
            f"(max range = {max_range} miles). "
            f"There may be a gap between consecutive stations exceeding "
            f"the vehicle range."
        )

    # ──────────────────────────────────────────────────────────────────────
    # Back-trace the optimal path
    # ──────────────────────────────────────────────────────────────────────
    path_indices: list[int] = []
    idx = dest_idx
    while idx != -1:
        path_indices.append(idx)
        idx = parent[idx]
    path_indices.reverse()

    fuel_stops: list[dict] = []
    total_gallons = 0.0

    for k in range(len(path_indices) - 1):
        i = path_indices[k]
        j = path_indices[k + 1]
        node_i = nodes[i]
        node_j = nodes[j]

        gap = node_j["distance_from_start"] - node_i["distance_from_start"]
        fuel_needed = gap / mpg
        fuel_cost = fuel_needed * node_i["price"]
        total_gallons += fuel_needed

        # Only include real stations (not start/destination)
        if not node_i["is_virtual"]:
            fuel_stops.append(
                {
                    "station_id": node_i["id"],
                    "name": node_i.get("name", ""),
                    "lat": node_i.get("lat"),
                    "lng": node_i.get("lng"),
                    "distance_from_start": round(node_i["distance_from_start"], 1),
                    "price_per_gallon": node_i["price"],
                    "gallons": round(fuel_needed, 2),
                    "cost": round(fuel_cost, 2),
                }
            )

    total_cost = round(dp[dest_idx], 2)
    logger.info(
        "Optimal fuel cost: $%.2f  |  %d stops  |  %.1f gallons",
        total_cost,
        len(fuel_stops),
        total_gallons,
    )

    return {
        "fuel_stops": fuel_stops,
        "total_fuel_cost": total_cost,
        "total_distance": round(total_distance, 1),
        "total_gallons": round(total_gallons, 2),
    }
