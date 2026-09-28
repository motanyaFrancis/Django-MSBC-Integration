from django.urls import path
from . import  views

urlpatterns = [
    # ---------- Imprest ----------
    path("ImprestRequisition/", views.ImprestRequisition.as_view(), name="ImprestRequisition"),
    path("ImprestRequisitionData/", views.ImprestRequisitionData.as_view(), name="ImprestRequisitionData"),
    path("ImprestDetail/<str:pk>", views.ImprestDetail.as_view(), name="ImprestDetail"),
    path("ImprestApproval/<str:pk>", views.ImprestApproval.as_view(), name="ImprestApproval"),
    path("CancelImprestApproval/<str:pk>", views.CancelImprestApproval.as_view(), name="CancelImprestApproval"),

    # ---------- Imprest Surrender ----------
    path("ImprestSurrender/", views.ImprestSurrender.as_view(), name="ImprestSurrender"),
    path("ImprestSurrenderData/", views.ImprestSurrenderData.as_view(), name="ImprestSurrenderData"),
    path("SurrenderDetail/<str:pk>", views.SurrenderDetail.as_view(), name="SurrenderDetail"),

    # ---------- Staff Claim ----------
    path("StaffClaim/", views.StaffClaim.as_view(), name="StaffClaim"),
    path("StaffClaimData/", views.StaffClaimData.as_view(), name="StaffClaimData"),
       # ==================== CLAIM DETAIL ====================
    path(
        'StaffClaim/<str:pk>/',
        views.ClaimDetailView.as_view(),
        name='ClaimDetail'
    ),
    path(
        'StaffClaim/<str:pk>/line/<int:line_no>/delete/',
        views.DeleteClaimLineView.as_view(),
        name='DeleteClaimLine'
    ),
 
    # ==================== ATTACHMENTS ====================
    path(
        'StaffClaim/<str:pk>/attachment/upload/',
        views.UploadClaimAttachmentView.as_view(),
        name='UploadClaimAttachment'
    ),
    path(
        'StaffClaim/<str:pk>/attachment/<str:line_no>/download/',
        views.DownloadClaimAttachmentView.as_view(),
        name='DownloadClaimAttachment'
    ),
    path(
        'StaffClaim/<str:pk>/attachment/<str:line_no>/delete/',
        views.DeleteClaimAttachmentView.as_view(),
        name='DeleteClaimAttachment'
    ),
 
    # ==================== APPROVAL WORKFLOW ====================
    path(
        'StaffClaim/<str:pk>/request-approval/',
        views.RequestClaimApprovalView.as_view(),
        name='RequestClaimApproval'
    ),
    path(
        'StaffClaim/<str:pk>/cancel-approval/',
        views.CancelClaimApprovalView.as_view(),
        name='CancelClaimApproval'
    ),

    # ---------- Shared attachments ----------
    path("finance-attachments/<str:pk>/", views.FinanceAttachments.as_view(), name="Finance_Attachments"),
    path("delete-finance-attachment/<str:pk>", views.DeleteFinanceAttachment.as_view(), name="Delete_Finance_Attacment"),
    path("GetDocumentAttachment/<str:pk>", views.GetDocumentAttachment.as_view(), name="GetDocumentAttachment"),
    
]