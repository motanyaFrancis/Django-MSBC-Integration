from django.urls import path
from . import views


urlpatterns = [
    path("upload-attachments/<str:pk>/", views.Attachments.as_view(), name="upload_attachments"),

    # Leave URLs
    path("leave/", views.LeaveRequest.as_view(), name="leave"),
    path('Leave_Data/', views.Leave_Data.as_view(), name='Leave_Data'),
    path("leave/<str:pk>/", views.LeaveDetail.as_view(), name="LeaveDetail"),
    path("LeaveAttachments/", views.LeaveAttachments.as_view(), name="LeaveAttachments"),
    path("Leave_Approvers_Data/", views.Leave_Approvers_Data.as_view(), name="Leave_Approvers_Data"),

    # Training URLs
    path("training/", views.TrainingRequest.as_view(), name="training"),
    path("training-data/", views.TrainingDataView.as_view(), name="training_Data"),
    path("training/<str:pk>", views.TrainingDetailsView.as_view(), name="training_details"),
    path("training-lines/<str:pk>/", views.TrainingLines.as_view(), name="training-lines"
    ),
    
    # Salary Advance

    
    # Employee transfers
    path('transfer/', views.TransferRequestView.as_view(), name="transfer"),
    path('transfer/<str:pk>', views.TransferDetailsView.as_view(), name="transfer_details"),
    path('submit-transfer/', views.SubmitTransfer.as_view(), name="submit_transfer"),

]
