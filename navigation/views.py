from grpc import services
from rest_framework.views import APIView
from .serlaizers import NavigationInputSerializer
from rest_framework.response import Response
from rest_framework import status
from . import services
class NavigationView(APIView):
    def post(self, request):
     try:
        serializer = NavigationInputSerializer(data=request.data)
        if serializer.is_valid():
            start = services.geocoding.geocode(serializer.validated_data['start'])
            end = services.geocoding.geocode(serializer.validated_data['end'])
            route = services.provider_call.get_route(
                start_lat=start[0],
                start_lng=start[1],
                end_lat=end[0],
                end_lng=end[1],
            )
            return Response({'path': route}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
     except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    