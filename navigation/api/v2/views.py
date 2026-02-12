from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import NavigationInputSerializer, NavigationOutputSerializer
from navigation.services import geocoding, provider_call, stations, optimizer, map_renderer

import logging

logger = logging.getLogger(__name__)


class NavigationView(APIView):
    """
    V2 navigation endpoint.

    Flow
    ----
    1. Geocode start / end.
    2. **First OSRM call** — base route A → B  (same as v1).
    3. Project stations using segment-projection algorithm (v2).
    4. Run DP optimizer on projected distances.
    5. **Second OSRM call** — route with waypoints
       (start → stop₁ → stop₂ → … → end) to get the real driving
       distance and production-ready polyline that includes detours.
    6. Return response with real distance / polyline from the second call
       while keeping the DP-optimal fuel cost.
    """

    def post(self, request):
        try:
            logger.debug("[v2] Received navigation request: %s", request.data)
            serializer = NavigationInputSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            data = serializer.validated_data
            start=geocoding.geocode(data["start"])
            end=geocoding.geocode(data["end"])
            #for testing
            #start =(41.8781, -87.6298)
            #end = (35.2271, -80.8431)
            route = provider_call.get_route(
                start_lat=start[0],
                start_lng=start[1],
                end_lat=end[0],
                end_lng=end[1],
            )

            route_stations = stations.get_stations_along_route_v2(
                route_points=route["points"],
                cumulative_distances=route["cumulative_distances"],
            )

            dp_result = optimizer.optimize_fuel_stops(
                stations=route_stations,
                total_distance=route["total_distance_miles"],
                max_range=data.get("max_range"),
                mpg=data.get("mpg"),
            )

            fuel_stops = dp_result["fuel_stops"]

            if fuel_stops:
                waypoints = [start]
                for stop in fuel_stops:
                    waypoints.append((stop["lat"], stop["lng"]))
                waypoints.append(end)

                validated = provider_call.get_route_with_waypoints(waypoints)
                real_distance = validated["total_distance_miles"]
                real_polyline = validated["route_polyline"]
            else:
                real_distance = route["total_distance_miles"]
                real_polyline = route["encoded_polyline"]

            result = {
                "total_distance_miles": round(real_distance, 1),
                "total_fuel_cost": dp_result["total_fuel_cost"],
                "total_gallons": dp_result["total_gallons"],
                "fuel_stops": fuel_stops,
                "route_polyline": real_polyline,
                "route_map": map_renderer.render_route_map(
                    encoded_polyline=real_polyline,
                    fuel_stops=fuel_stops,
                ),
            }

            output = NavigationOutputSerializer(result)
            return Response(output.data, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning("Validation error: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            logger.error("Service unavailable: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unhandled error in v2 NavigationView")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
