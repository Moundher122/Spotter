"""
Unit tests for the fuel-cost optimizer (forward DP).

These are pure-logic tests — no database, no network.
"""

from django.test import TestCase, override_settings

from navigation.services.optimizer import optimize_fuel_stops

FUEL_SETTINGS = {
    "MAX_RANGE_MILES": 500,
    "MPG": 10,
    "MAX_STATION_DISTANCE_FROM_ROUTE_MILES": 25,
    "OSRM_BASE_URL": "http://router.project-osrm.org/route/v1/driving",
    "NOMINATIM_URL": "https://nominatim.openstreetmap.org/search",
    "NOMINATIM_USER_AGENT": "test-agent",
}


@override_settings(FUEL_OPTIMIZER=FUEL_SETTINGS)
class OptimizerTests(TestCase):
    """Test optimize_fuel_stops with synthetic station data."""

    def _make_station(self, sid, distance, price):
        return {
            "id": sid,
            "name": f"Station {sid}",
            "lat": 40.0,
            "lng": -90.0,
            "price": price,
            "distance_from_start": distance,
        }

    # ------------------------------------------------------------------
    # 1. Single station, short route
    # ------------------------------------------------------------------
    def test_single_station(self):
        # Route of 600 miles forces a stop (max_range=500)
        stations = [self._make_station(1, 300.0, 3.50)]
        result = optimize_fuel_stops(stations, total_distance=600.0)

        self.assertEqual(len(result["fuel_stops"]), 1)
        # start→station1 is free (price=0), station1→dest costs 300/10*3.50=105
        expected_cost = (300.0 / 10) * 3.50  # only the station→dest leg
        self.assertAlmostEqual(result["total_fuel_cost"], expected_cost, places=2)
        self.assertAlmostEqual(result["total_gallons"], 60.0, places=2)

    # ------------------------------------------------------------------
    # 2. Chooses the cheapest station when both are reachable
    # ------------------------------------------------------------------
    def test_chooses_cheapest(self):
        # Route of 900 miles forces at least 2 stops (max_range=500)
        stations = [
            self._make_station(1, 200.0, 5.00),  # expensive
            self._make_station(2, 400.0, 2.00),  # cheap
            self._make_station(3, 700.0, 4.00),  # mid-price
        ]
        result = optimize_fuel_stops(stations, total_distance=900.0)

        stop_ids = [s["station_id"] for s in result["fuel_stops"]]
        # The cheap station 2 should be selected
        self.assertIn(2, stop_ids)
        self.assertGreater(len(result["fuel_stops"]), 0)

    # ------------------------------------------------------------------
    # 3. Unreachable destination raises ValueError
    # ------------------------------------------------------------------
    def test_unreachable_raises(self):
        # Gap of 600 miles with max_range=500 → unreachable
        stations = [
            self._make_station(1, 100.0, 3.00),
            self._make_station(2, 700.0, 3.00),  # 600-mile gap
        ]
        with self.assertRaises(ValueError):
            optimize_fuel_stops(stations, total_distance=800.0)

    # ------------------------------------------------------------------
    # 4. Empty stations list – start directly to destination
    # ------------------------------------------------------------------
    def test_no_stations_short_route(self):
        result = optimize_fuel_stops([], total_distance=300.0)
        # Route < 500 miles → short-route fast-path, zero stops, zero cost
        self.assertEqual(len(result["fuel_stops"]), 0)
        self.assertAlmostEqual(result["total_fuel_cost"], 0.0, places=2)
        # Still reports how many gallons the trip consumes
        self.assertAlmostEqual(result["total_gallons"], 30.0, places=2)

    # ------------------------------------------------------------------
    # 5. Custom mpg and max_range
    # ------------------------------------------------------------------
    def test_custom_vehicle_params(self):
        stations = [
            self._make_station(1, 200.0, 4.00),
        ]
        result = optimize_fuel_stops(
            stations, total_distance=400.0, max_range=450, mpg=20
        )
        # 400 < 450 → short-route fast-path, zero stops, zero cost
        self.assertEqual(len(result["fuel_stops"]), 0)
        self.assertAlmostEqual(result["total_fuel_cost"], 0.0, places=2)
        # 400 miles / 20 mpg = 20 gallons total
        self.assertAlmostEqual(result["total_gallons"], 20.0, places=2)

    # ------------------------------------------------------------------
    # 6. Many stations — optimizer still completes
    # ------------------------------------------------------------------
    def test_many_stations(self):
        stations = [
            self._make_station(i, i * 50.0, 3.00 + (i % 5) * 0.10)
            for i in range(1, 30)
        ]
        result = optimize_fuel_stops(stations, total_distance=1500.0)
        self.assertGreater(len(result["fuel_stops"]), 0)
        self.assertGreater(result["total_fuel_cost"], 0)

    # ------------------------------------------------------------------
    # 7. Output shape is correct
    # ------------------------------------------------------------------
    def test_output_keys(self):
        # Route of 800 miles forces a stop (max_range=500)
        stations = [
            self._make_station(1, 200.0, 3.00),
            self._make_station(2, 500.0, 3.50),
        ]
        result = optimize_fuel_stops(stations, total_distance=800.0)

        self.assertIn("fuel_stops", result)
        self.assertIn("total_fuel_cost", result)
        self.assertIn("total_distance", result)
        self.assertIn("total_gallons", result)
        self.assertGreater(len(result["fuel_stops"]), 0)

        stop = result["fuel_stops"][0]
        for key in (
            "station_id", "name", "lat", "lng",
            "distance_from_start", "price_per_gallon",
            "gallons", "cost",
        ):
            self.assertIn(key, stop)

    # ------------------------------------------------------------------
    # 8. Short route (< max_range) returns zero cost immediately
    # ------------------------------------------------------------------
    def test_short_route_zero_cost(self):
        """If total_distance ≤ max_range the truck goes straight through."""
        stations = [
            self._make_station(1, 100.0, 3.00),
            self._make_station(2, 200.0, 4.00),
        ]
        result = optimize_fuel_stops(stations, total_distance=450.0)
        self.assertEqual(result["fuel_stops"], [])
        self.assertEqual(result["total_fuel_cost"], 0.0)
        self.assertAlmostEqual(result["total_gallons"], 45.0, places=2)
        self.assertAlmostEqual(result["total_distance"], 450.0, places=1)
