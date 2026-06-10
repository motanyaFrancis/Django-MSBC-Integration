from django.urls import path
from . import views

urlpatterns = [
    path('resignation/',views.Resignation.as_view(),name='resignation'),
    path('clearance/',views.Clearance.as_view(),name='clearance'),
    path('submitClearance/<str:pk>/', views.SubmitClearance.as_view(), name="submitClearance"),
    # path('QyHrmExitHeader/',views.QyHrmExitHeader.as_view(),name='QyHrmExitHeader'),
    path('ClearanceApprovalRequest/',views.ClearanceApprovalRequest.as_view(),name='ClearanceApprovalRequest'),
]