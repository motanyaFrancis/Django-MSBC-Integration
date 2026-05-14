from django.urls import path
from . import views


urlpatterns = [
    path("leave/", views.LeaveRequest.as_view(), name="leave"),
    path('Leave_Data/', views.Leave_Data.as_view(), name='Leave_Data'),
    path("leave/<str:pk>/", views.LeaveDetail.as_view(), name="LeaveDetail"),
    path("LeaveAttachments/", views.LeaveAttachments.as_view(), name="LeaveAttachments"),
    path("Leave_Approvers_Data/", views.Leave_Approvers_Data.as_view(), name="Leave_Approvers_Data"),
]
