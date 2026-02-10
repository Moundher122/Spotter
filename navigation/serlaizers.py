from rest_framework import serializers


class NavigationInputSerializer(serializers.Serializer):
    start = serializers.CharField()
    end = serializers.CharField()
    