from rest_framework.views import APIView
from .serlaizers import NavigationInputSerializer
from rest_framework.response import Response
from rest_framework import status

class NavigationView(APIView):
    def post(self, request):
        serializer = NavigationInputSerializer(data=request.data)
        if serializer.is_valid():
            start = serializer.validated_data['start']
            end = serializer.validated_data['end']
            return Response({'path': start}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    