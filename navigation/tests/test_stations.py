"""
Unit tests for the station-projection service.

Uses Django's test framework with an in-memory PostGIS database.
"""

from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point

from gasstation.models import GasStation
from navigation.services.stations import get_stations_along_route
from navigation.services.helper import haversine, compute_cumulative_distances

FUEL_SETTINGS = {
    "MAX_RANGE_MILES": 500,
    "MPG": 10,
    "MAX_STATION_DISTANCE_FROM_ROUTE_MILES": 25,
    "OSRM_BASE_URL": "http://router.project-osrm.org/route/v1/driving",
    "NOMINATIM_URL": "https://nominatim.openstreetmap.org/search",
    "NOMINATIM_USER_AGENT": "test-agent",
}


@override_settings(FUEL_OPTIMIZER=FUEL_SETTINGS)
class StationsServiceTests(TestCase):
    """Test get_stations_along_route with real PostGIS queries."""

    @classmethod
    def setUpTestData(cls):
        """Create a few gas stations for testing."""
        GasStation.objects.create(
            opis_id=1,
            name="Near Route Station",
            address="123 Main St",
            city="Springfield",
            state="IL",
            rack_id=100,
            retail_price=3.50,
            location=Point(-85.0, 40.0, srid=4326),
        )
        GasStation.objects.create(
            opis_id=2,
            name="Far Away Station",
            address="456 Other St",
            city="Nowhere",
            state="TX",
            rack_id=200,
            retail_price=2.99,
            location=Point(-95.0, 30.0, srid=4326),
        )
        GasStation.objects.create(
            opis_id=3,
            name="Also Near Route",
            address="789 Route Rd",
            city="Columbus",
            state="OH",
            rack_id=300,
            retail_price=3.20,
            location=Point(-82.0, 40.0, srid=4326),
        )

    def _simple_route(self):
        """Straight west-to-east route at lat=40, lng from -90 to -80."""
        points = [(40.0, -90.0 + i * 0.1) for i in range(101)]
        cumulative = compute_cumulative_distances(points)
        return points, cumulative

    def test_finds_stations_near_route(self):
        points, cumulative = self._simple_route()
        result = get_stations_along_route(points, cumulative)

        found_ids = {s["id"] for s in result}
        self.assertIn(1, found_ids)
        self.assertIn(3, found_ids)

    def test_excludes_far_stations(self):
        points, cumulative = self._simple_route()
        result = get_stations_along_route(points, cumulative)

        found_ids = {s["id"] for s in result}
        self.assertNotIn(2, found_ids)

    def test_sorted_by_distance(self):
        points, cumulative = self._simple_route()
        result = get_stations_along_route(points, cumulative)

        distances = [s["distance_from_start"] for s in result]
        self.assertEqual(distances, sorted(distances))

    def test_station_dict_keys(self):
        points, cumulative = self._simple_route()
        result = get_stations_along_route(points, cumulative)

        if result:
            station = result[0]
            for key in ("id", "name", "lat", "lng", "price",
                        "distance_from_start", "distance_from_route"):
                self.assertIn(key, station)


class HaversineTests(TestCase):
    """Sanity-check the haversine helper."""

    def test_same_point_zero(self):
        self.assertAlmostEqual(haversine(40, -90, 40, -90), 0.0, places=5)

    def test_known_distance(self):
        d = haversine(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertAlmostEqual(d, 2451, delta=50)

    def test_cumulative_distances(self):
        points = [(40.0, -90.0), (40.0, -89.0), (40.0, -88.0)]
        cum = compute_cumulative_distances(points)
        self.assertEqual(len(cum), 3)
        self.assertEqual(cum[0], 0.0)
        self.assertGreater(cum[1], 0)
        self.assertGreater(cum[2], cum[1])
