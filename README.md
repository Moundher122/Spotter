# Spotter

A REST API that finds the **cheapest fuel stops** for a truck traveling between two locations across the US.  
Given a start and end point, it returns the optimal set of gas stations to stop at along the driving route to minimize total fuel cost.

---

## How It Works

1. **Geocode** the start and end locations into GPS coordinates.
2. **Fetch the driving route** between them (polyline + distance).
3. **Find gas stations** near the route from the database.
4. **Optimize** which stations to stop at using dynamic programming to get the lowest total fuel cost.
5. **Return** the optimal stops, cost breakdown, and route polyline.

There are two API versions:

- **[v1](v1.md)** — Single OSRM call, nearest-point station projection, returns the base route geometry.
- **[v2](v2.md)** — Two OSRM calls, perpendicular segment projection for better accuracy, returns the real driving geometry through fuel stops including detour distances.

See each doc for full algorithm details, function-by-function breakdowns, and response formats.

---

## API

### v1: `POST /api/v1/navigate/`

Full documentation: **[v1.md](v1.md)**

**Request:**
```json
{
  "start": "New York, NY",
  "end": "Los Angeles, CA"
}
```

**Response:**
```json
{
  "fuel_stops": [ ... ],
  "total_fuel_cost": 487.32,
  "total_distance": 2790.4,
  "total_gallons": 279.04,
  "encoded_polyline": "a~l~Fjk~uOwHJy@..."
}
```

### v2: `POST /api/v2/navigate/`

Full documentation: **[v2.md](v2.md)**

**Request:** same as v1.

**Response:**
```json
{
  "total_distance_miles": 2805.3,
  "total_fuel_cost": 487.32,
  "total_gallons": 279.04,
  "fuel_stops": [ ... ],
  "route_polyline": "a~l~Fjk~uOwHJy@..."
}
```

Key differences: `total_distance_miles` and `route_polyline` come from a second OSRM call that routes through the actual fuel stops, giving real driving distance including detours.

---

## Tech Stack & Why

| Technology | What | Why |
|---|---|---|
| **Django** | Web framework | Mature, batteries-included, great ORM and management commands for data import |
| **Django REST Framework** | API layer | Clean serializers, request validation, and response formatting out of the box |
| **PostGIS** | Spatial database (PostgreSQL extension) | Enables geographic queries — finding stations within a bounding box using spatial indexing, far faster than computing distances in Python |
| **GeoPy** | Geocoding library | Converts place names ("New York, NY") to coordinates via Nominatim |
| **Polyline** | Route geometry decoder | Decodes the compressed polyline format returned by OSRM into lat/lng coordinate lists |
| **OSRM** | Routing engine (external API) | Open-source driving directions — provides the actual road route, distance, and geometry between two points |
| **psycopg2** | PostgreSQL adapter | Required for Django to talk to PostgreSQL/PostGIS |
| **python-decouple** | Environment config | Keeps secrets (DB credentials, API keys) out of the codebase via `.env` files |
| **uv** | Python package manager | Fast dependency resolution and installs, used both locally and in Docker |
| **Docker** | Containerization | Reproducible environment — bundles GDAL/GEOS spatial libraries that PostGIS needs |

---

## Project Structure

```
spotter/
├── spotter/              # Django project settings & URL config
├── navigation/           # Main app — API views, services, tests
│   ├── api/
│   │   ├── v1/               # v1 endpoint (views, serializers, urls)
│   │   └── v2/               # v2 endpoint (views, serializers, urls)
│   ├── services/
│   │   ├── geocoding.py      # Place name → (lat, lng)
│   │   ├── provider_call.py  # OSRM route fetching (base + waypoints)
│   │   ├── stations.py       # Find & project stations (v1 + v2 algorithms)
│   │   ├── optimizer.py      # Forward DP for cheapest fuel stops
│   │   ├── helper.py         # Haversine, segment projection, cumulative distances
│   │   └── converter.py      # Unit conversions (meters ↔ miles)
│   └── tests/
├── gasstation/           # Gas station model + CSV import command
│   ├── models.py         # GasStation (PostGIS PointField)
│   └── management/commands/import_gasstations.py
├── Data/
│   └── gasstations.csv   # Station dataset (OPIS)
├── v1.md                 # v1 algorithm documentation
├── v2.md                 # v2 algorithm documentation
├── docker-compose.yaml   # PostGIS database
├── dockerfile            # App container (Python + GDAL)
└── pyproject.toml        # Dependencies
```

---

## Setup

### 1. Start the database
```bash
docker compose up -d
```

### 2. Configure environment
Create a `.env` file:
```
SECRET_KEY=your-secret-key
DEBUG=True
POSTGRES_DB=spotter_db
POSTGRES_USER=spotter_user
POSTGRES_PASSWORD=spotter_password
```

### 3. Install dependencies & run
```bash
uv sync
uv run manage.py migrate
uv run manage.py import_gasstations
uv run manage.py runserver
```

### 4. Test the API
```bash
# v1
curl -X POST http://localhost:8000/api/v1/navigate/ \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "end": "Los Angeles, CA"}'

# v2
curl -X POST http://localhost:8000/api/v2/navigate/ \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "end": "Los Angeles, CA"}'
```

---

## Configuration

Defaults in `spotter/settings.py` under `FUEL_OPTIMIZER`:

| Setting | Default | Meaning |
|---|---|---|
| `MAX_RANGE_MILES` | 500 | Truck's maximum range on a full tank |
| `MPG` | 10 | Fuel efficiency (miles per gallon) |
| `MAX_STATION_DISTANCE_FROM_ROUTE_MILES` | 25 | Max distance a station can be from the route to be considered |
| `OSRM_BASE_URL` | OSRM public API | Routing service endpoint |
