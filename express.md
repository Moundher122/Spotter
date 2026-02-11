# Fuel-Optimized Route Navigation — Algorithm Explained

## Overview

This system finds the **cheapest set of fuel stops** for a truck traveling a fixed route from point A to point B. The route itself is not optimized — it is fetched from OSRM. What *is* optimized is **where and how much fuel to buy** along that route to minimize total fuel cost.

The core technique is **Forward Dynamic Programming (DP)**.

---

## End-to-End Pipeline

The full request flows through these stages:

```
User Request (start, end)
       │
       ▼
 ① Geocoding          → Convert place names to (lat, lng)
       │
       ▼
 ② Route Fetching     → Get driving route from OSRM
       │
       ▼
 ③ Station Projection → Find gas stations near the route
       │
       ▼
 ④ DP Optimization    → Choose optimal fuel stops
       │
       ▼
 API Response          → Stops, cost, gallons, polyline
```

---

## Step ①  — Geocoding

**File:** `navigation/services/geocoding.py`

Converts human-readable location names (e.g. `"New York, NY"`) into geographic coordinates `(latitude, longitude)` using the geopy Nominatim geocoder.

**Input:** `"Los Angeles, CA"`  
**Output:** `(34.0522, -118.2437)`

---

## Step ②  — Route Fetching

**File:** `navigation/services/provider_call.py`

Calls the **OSRM** (Open Source Routing Machine) API to get the actual driving route between the two geocoded points.

### What happens:
1. Sends a request to OSRM: `GET /route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=polyline`
2. Receives an encoded polyline (compressed representation of the route geometry) and total distance in meters.
3. **Decodes** the polyline into a list of `(lat, lng)` coordinate points using the `polyline` library.
4. **Converts** the total distance from meters to miles.
5. **Computes cumulative distances** — for each point on the decoded polyline, calculates how many miles it is from the start using the Haversine formula.

### Output:
| Field                   | Description                                 |
|-------------------------|---------------------------------------------|
| `encoded_polyline`      | Compressed route geometry for the frontend  |
| `points`                | Decoded list of `(lat, lng)` tuples         |
| `cumulative_distances`  | Miles from start for each polyline point    |
| `total_distance_miles`  | Total driving distance in miles             |

---

## Step ③  — Station Projection

**File:** `navigation/services/stations.py`

Finds gas stations from the PostGIS database that lie near the route and computes how far along the route each station is.

### Sub-steps:

1. **Bounding box** — Compute the min/max lat/lng of all route points, pad by 0.5° (~35 miles), and form a rectangle.

2. **Database query** — Use PostGIS `__within` to fetch all `GasStation` records whose `location` (PointField) falls inside the bounding box.

3. **Sub-sample route** — The decoded polyline can have tens of thousands of points. Sub-sample down to ~2000 evenly spaced points for performance.

4. **Project each station** — For every station returned from the DB:
   - Loop through the sampled route points.
   - Use the **Haversine formula** to compute the great-circle distance between the station and each route point.
   - Record the closest route point and its cumulative distance — this becomes the station's `distance_from_start`.

5. **Filter** — Discard stations that are:
   - More than `MAX_STATION_DISTANCE_FROM_ROUTE_MILES` away from the route (too far off the highway).
   - Beyond `MAX_RANGE_MILES` from the start (truck can never reach them on a full tank from start anyway).

6. **Sort** — Order all surviving stations by `distance_from_start` (ascending).

### Output per station:
| Field                 | Description                                    |
|-----------------------|------------------------------------------------|
| `id`                  | OPIS ID (primary key)                          |
| `name`                | Station name                                   |
| `lat`, `lng`          | Station coordinates                            |
| `price`               | Retail price per gallon                        |
| `distance_from_start` | Miles along the route from the starting point  |
| `distance_from_route` | Perpendicular distance from the route (miles)  |

---

## Step ④  — Forward Dynamic Programming Optimization

**File:** `navigation/services/optimizer.py`

This is the core algorithm. Given the sorted list of stations and the total route distance, it finds the **globally minimum fuel cost** to reach the destination.

### Key parameters:
| Parameter    | Default | Meaning                                    |
|--------------|---------|--------------------------------------------|
| `max_range`  | 500 mi  | Maximum distance the truck can drive on a full tank |
| `mpg`        | 10      | Fuel efficiency (miles per gallon)         |

### Fast path — No stops needed:
If `total_distance ≤ max_range`, the truck can make the entire trip on a single tank. The algorithm returns immediately with **zero fuel cost** and no stops.

### Node construction:
The algorithm builds an ordered list of **nodes**:

```
Node 0 (Start)  →  Node 1 (Station A)  →  Node 2 (Station B)  →  ...  →  Node N-1 (Destination)
```

- **Start node** — virtual, `distance_from_start = 0`, `price = 0` (no fuel purchased here; truck is assumed to start with a full tank).
- **Station nodes** — real stations sorted by `distance_from_start`, each with a fuel `price`.
- **Destination node** — virtual, `distance_from_start = total_distance`, `price = 0`.

### The DP recurrence:

Define:

$$dp[i] = \text{minimum total fuel cost to reach node } i$$

**Base case:**

$$dp[0] = 0 \quad \text{(start node — no cost)}$$

**Transition:** For each node $i$ (in order), try fueling at node $i$ and driving to every reachable node $j$ where $j > i$:

$$\text{gap} = \text{distance}[j] - \text{distance}[i]$$

$$\text{fuel\_needed} = \frac{\text{gap}}{\text{mpg}} \quad \text{(gallons)}$$

$$\text{fuel\_cost} = \text{fuel\_needed} \times \text{price}[i]$$

$$dp[j] = \min\bigl(dp[j],\; dp[i] + \text{fuel\_cost}\bigr)$$

**Constraint:** The gap must satisfy $0 < \text{gap} \leq \text{max\_range}$. If the gap exceeds the tank range, node $j$ is unreachable directly from node $i$ and the inner loop breaks (since nodes are sorted by distance).

### Parent tracking:
A `parent[j]` array records which node $i$ led to the optimal cost at $j$. This enables back-tracing.

### Feasibility check:
After the DP completes, if `dp[destination] = ∞`, it means the destination is unreachable — there is a gap between consecutive stations that exceeds `max_range`. A `ValueError` is raised.

### Back-trace:
Starting from the destination node, follow the `parent` pointers back to the start to reconstruct the optimal path:

```
destination → parent[destination] → parent[parent[destination]] → ... → start
```

Reverse this to get the forward path. For each consecutive pair of nodes $(i, j)$ on the path, compute the fuel purchased at node $i$ and the cost. Virtual nodes (start/destination) are excluded from the output.

### Output:
| Field              | Description                                           |
|--------------------|-------------------------------------------------------|
| `fuel_stops`       | List of stations where the truck should stop and refuel |
| `total_fuel_cost`  | Globally minimum cost in dollars                      |
| `total_distance`   | Total route distance in miles                         |
| `total_gallons`    | Total fuel consumed in gallons                        |

Each fuel stop includes:
| Field                 | Value                                  |
|-----------------------|----------------------------------------|
| `station_id`          | OPIS ID                                |
| `name`                | Station name                           |
| `lat`, `lng`          | Coordinates                            |
| `distance_from_start` | Miles from the route origin            |
| `price_per_gallon`    | Price at this station                  |
| `gallons`             | How many gallons to buy here           |
| `cost`                | Cost at this stop ($)                  |

---

## Worked Example

Suppose:
- **Route:** 1200 miles total
- **Max range:** 500 miles
- **MPG:** 10
- **Stations (sorted):**

| Station | Distance from Start | Price ($/gal) |
|---------|--------------------:|:-------------:|
| A       | 150 mi              | $3.00         |
| B       | 400 mi              | $2.50         |
| C       | 700 mi              | $3.20         |
| D       | 1000 mi             | $2.80         |

**Nodes:** `[Start(0), A(150), B(400), C(700), D(1000), Dest(1200)]`

The DP explores every reachable pair:
- From **Start** (price $0): driving to A/B costs $0 (virtual node, no fuel purchase).
- From **A** (price $3.00): fuel cost to reach B = (250/10) × 3.00 = $75, to C = (550 > 500) → unreachable.
- From **B** (price $2.50): fuel cost to reach C = (300/10) × 2.50 = $75, to D = (600 > 500) → unreachable.
- …and so on.

The DP finds the combination of stops that yields the absolute minimum total cost, considering **all** possible stop sequences — not just greedy choices.

---

## Why Dynamic Programming instead of Greedy?

A **greedy** approach (e.g., always pick the cheapest reachable station) can fail because:
- A slightly more expensive nearby station might allow reaching a much cheaper station further ahead.
- The cheapest local choice does not guarantee the cheapest global path.

**Forward DP** considers every valid combination and guarantees the **globally optimal** solution.

### Complexity:
- **Time:** $O(n^2)$ where $n$ = number of nodes (stations + 2). For each node, we scan forward until exceeding `max_range`.
- **Space:** $O(n)$ for the `dp` and `parent` arrays.

In practice, $n$ is typically in the hundreds to low thousands, making this very fast.

---

## Supporting Utilities

| File                | Purpose                                              |
|---------------------|------------------------------------------------------|
| `converter.py`      | Unit conversion — meters ↔ miles                     |
| `helper.py`         | `haversine()` — great-circle distance between two coordinates; `compute_cumulative_distances()` — cumulative mileage along a polyline |
| `geocoding.py`      | Geocode place names to `(lat, lng)`                  |
| `provider_call.py`  | Fetch driving route from OSRM                        |
| `stations.py`       | Query PostGIS DB & project stations onto the route    |
| `optimizer.py`      | Forward DP for optimal fuel stops                    |

---

## Data Model

**`GasStation`** (PostGIS-backed Django model):

| Field          | Type              | Description                    |
|----------------|-------------------|--------------------------------|
| `opis_id`      | Integer (PK)      | Unique station identifier      |
| `name`         | CharField         | Station name                   |
| `address`      | TextField         | Full address                   |
| `city`         | CharField         | City                           |
| `state`        | CharField         | State code                     |
| `rack_id`      | Integer           | Rack identifier                |
| `retail_price` | Decimal(8,4)      | Fuel price per gallon          |
| `location`     | PointField (4326) | Geographic coordinates (WGS84) |
