from django.urls import path
from . import views
urlpatterns = [
    path("transport/", views.TransportRequest.as_view(), name="transport"),
    path("transport/<str:pk>/", views.TransportDetails.as_view(), name="TransportDetails"),
    path("SubmitTransport/<str:pk>/", views.SubmitTransport.as_view(), name="SubmitTransport"),
]