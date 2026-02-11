import csv
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from geopy.geocoders import Nominatim
from gasstation.models import TruckStop

class Command(BaseCommand):
    help = "Import gasstations from CSV and add geometry"

    def handle(self, *args, **kwargs):
        geolocator = Nominatim(user_agent="gasstation_django")

        with open("Data/gasstations.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                full_address = f"{row['Address']}, {row['City']}, {row['State']}, USA"

                try:
                    location = geolocator.geocode(full_address)
                    if not location:
                        self.stdout.write(f"Not found: {full_address}")
                        continue

                    point = Point(location.longitude, location.latitude)

                    TruckStop.objects.update_or_create(
                        opis_id=row['OPIS Truckstop ID'],
                        defaults={
                            'name': row['Truckstop Name'],
                            'address': row['Address'],
                            'city': row['City'],
                            'state': row['State'],
                            'rack_id': row['Rack ID'],
                            'retail_price': row['Retail Price'],
                            'location': point,
                        }
                    )

                    time.sleep(1)  # Nominatim rate limit

                except Exception as e:
                    self.stderr.write(str(e))
