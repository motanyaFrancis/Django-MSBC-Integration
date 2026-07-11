from django.urls import path
from . import views

urlpatterns = [
    path("ImprestRequisition/", views.ImprestRequisition.as_view(), name="ImprestRequisition"),
    path("ImprestRequisitionData/", views.ImprestRequisitionData.as_view(), name="ImprestRequisitionData"),
    path("ImprestDetail/<str:pk>", views.ImprestDetail.as_view(), name="ImprestDetail"),
    path("ImprestSurrender/", views.ImprestSurrender.as_view(), name="ImprestSurrender"),
    path("ImprestSurrenderData/", views.ImprestSurrenderData.as_view(), name="ImprestSurrenderData"),
    path("surrenderDetail/<str:pk>", views.surrenderDetail.as_view(), name="surrenderDetail"),
    path("StaffClaim/", views.StaffClaim.as_view(), name="StaffClaim"),
    path("StaffClaimData/", views.StaffClaimData.as_view(), name="StaffClaimData"),
    path("ClaimDetail/<str:pk>", views.ClaimDetail.as_view(), name="ClaimDetail"),
    path("claimApproval/<str:pk>", views.claimApproval.as_view(), name="claimApproval"),
    path("UploadFinaceAttachment/<str:pk>", views.UploadFinaceAttachment.as_view(), name="UploadFinaceAttachment"),
    path("GetDocumentAttachment/<str:pk>", views.GetDocumentAttachment.as_view(), name="GetDocumentAttachment"),
    path("imprestApproval/<str:pk>", views.imprestApproval.as_view(), name="imprestApproval"),
    path("cancelImprestApproval/<str:pk>", views.cancelImprestApproval.as_view(), name="cancelImprestApproval"),
]