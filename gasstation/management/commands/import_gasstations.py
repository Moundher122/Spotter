import csv
import time
import os
import re

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from geopy.geocoders import Nominatim
from gasstation.models import GasStation


def split_address_only(address_part):
    """
    Split ONLY the road part (row['Address'])

    Example:
    I-44, EXIT 283 & US-69
    ->
    ["I-44", "US-69"]
    """

    if "&" not in address_part:
        return [address_part.strip()]

    address_part = re.sub(
        r"EXIT\s*\d+[-A-Z]*",
        "",
        address_part,
        flags=re.IGNORECASE
    )

    address_part = address_part.replace(",", "")

    roads = [r.strip() for r in address_part.split("&") if r.strip()]

    return roads


class Command(BaseCommand):
    help = "Import gasstations from CSV and add geometry"

    def handle(self, *args, **kwargs):

        geolocator = Nominatim(
            user_agent="gasstation_django (bouroumanamoundher@gmail.com)"
        )

        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', 'Data', 'gasstations.csv'
        )
        csv_path = os.path.normpath(csv_path)

        if not os.path.exists(csv_path):
            self.stderr.write(f"CSV file not found at: {csv_path}")
            return

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:

                address_part = row['Address']
                city = row['City']
                state = row['State']

                full_address = f"{address_part}, {city}, {state}, USA"

                try:
                    location = geolocator.geocode(full_address, timeout=10)
                    if not location and "&" in address_part:
                        self.stdout.write(f"Trying split for: {full_address}")
                        roads = split_address_only(address_part)
                        for road in roads:
                            alt_address = f"{road}, {city}, {state}, USA"
                            self.stdout.write(f"Trying: {alt_address}")

                            location = geolocator.geocode(
                                alt_address,
                                timeout=10
                            )
                            if location:
                                break
                    if not location:
                        city_only = f"{city}, {state}, USA"
                        self.stdout.write(f"Trying city fallback: {city_only}")
                        location = geolocator.geocode(
                            city_only,
                            timeout=10
                        )
                    if not location:
                        self.stdout.write(f"Not found: {full_address}")
                        continue
                    point = Point(
                        location.longitude,
                        location.latitude
                    )
                    GasStation.objects.update_or_create(
                        opis_id=row['OPIS Truckstop ID'],
                        defaults={
                            'name': row['Truckstop Name'],
                            'address': address_part,
                            'city': city,
                            'state': state,
                            'rack_id': row['Rack ID'],
                            'retail_price': row['Retail Price'],
                            'location': point,
                        }
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Saved: {row['Truckstop Name']}"
                        )
                    )

                    time.sleep(1.1)

                except Exception as e:
                    self.stderr.write(str(e))
