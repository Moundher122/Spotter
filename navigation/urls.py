from django.urls import path, include

urlpatterns = [
    path('v1/', include('navigation.api.v1.urls')),
    path('v2/', include('navigation.api.v2.urls')),
]