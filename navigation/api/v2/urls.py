from django.urls import path
from . import views

urlpatterns = [
    path('navigate/', views.NavigationView.as_view(), name='v2-navigate'),
]
