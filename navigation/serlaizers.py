from rest_framework import serializers


class NavigationInputSerializer(serializers.Serializer):
    start = serializers.CharField()
    end = serializers.CharField()
class NavigationOutputSerializer(serializers.Serializer):
    path = serializers.ListField(
        child=serializers.DictField(child=serializers.FloatField())
    )
    