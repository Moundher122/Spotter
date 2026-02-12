from rest_framework import serializers


class NavigationInputSerializer(serializers.Serializer):
    start = serializers.CharField()
    end = serializers.CharField()


class FuelStopSerializer(serializers.Serializer):
    station_id = serializers.IntegerField()
    name = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    distance_from_start = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    gallons = serializers.FloatField()
    cost = serializers.FloatField()


class NavigationOutputSerializer(serializers.Serializer):
    fuel_stops = FuelStopSerializer(many=True)
    total_fuel_cost = serializers.FloatField()
    total_distance = serializers.FloatField()
    total_gallons = serializers.FloatField()
    encoded_polyline = serializers.CharField()
