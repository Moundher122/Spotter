from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import NavigationInputSerializer, NavigationOutputSerializer
from navigation.services import geocoding, provider_call, stations, optimizer

import logging

logger = logging.getLogger(__name__)


class NavigationView(APIView):
    def post(self, request):
        try:
            logger.debug("Received navigation request with data: %s", request.data)
            serializer = NavigationInputSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            data = serializer.validated_data


            start =(41.8781, -87.6298)
            end = (35.2271, -80.8431)

            route = provider_call.get_route(
                start_lat=start[0],
                start_lng=start[1],
                end_lat=end[0],
                end_lng=end[1],
            )

            route_stations = stations.get_stations_along_route(
                route_points=route["points"],
                cumulative_distances=route["cumulative_distances"],
            )

            result = optimizer.optimize_fuel_stops(
                stations=route_stations,
                total_distance=route["total_distance_miles"],
                max_range=data.get("max_range"),
                mpg=data.get("mpg"),
            )

            result["encoded_polyline"] = route["encoded_polyline"]

            output = NavigationOutputSerializer(result)
            return Response(output.data, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.warning("Validation error: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            logger.error("Service unavailable: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unhandled error in NavigationView")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
