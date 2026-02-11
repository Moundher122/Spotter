from django.contrib.gis.db import models

class GasStation(models.Model):
    opis_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=10)
    rack_id = models.IntegerField()
    retail_price = models.DecimalField(max_digits=8, decimal_places=4)

    location = models.PointField(geography=True)

    def __str__(self):
        return self.name
