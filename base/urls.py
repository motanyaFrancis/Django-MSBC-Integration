from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("get_destinations/", views.Destinations.as_view(), name="get_destinations"),
]