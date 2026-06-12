from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("get_destinations/", views.Destinations.as_view(), name="get_destinations"),
    path("get-dimensions/", views.Dimensions.as_view(), name="get_dimensions"),
    path("get-training-needs/", views.TrainingNeeds.as_view(), name="get_training_needs"),
    path("get-leave-balance/", views.LeaveBalanceView.as_view(), name="get_leave_balance"),
    path('get-user-report/', views.UserReportView.as_view(), name='get_user_report'),
    path('generate-report/', views.ReportGeneratorView.as_view(), name='generate_report'),
    path('get-units-of-measure/', views.UnitOfMeasure.as_view(), name='get_units_of_measure'),
    path('get-items/', views.Items.as_view(), name='get_items'),
]
