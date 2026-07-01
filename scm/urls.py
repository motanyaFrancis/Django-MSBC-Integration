from django.urls import path
from . import views

urlpatterns = [
    path("purchase/", views.PurchaseRequest.as_view(), name="purchase"),
    path("purchase/<str:pk>/", views.PurchaseDetails.as_view(), name="purchase_details"),
    path("purchase-approval/<str:pk>/", views.PurchaseApproval.as_view(), name="purchase_aproval"),
    path("cancel-purchase-approval/<str:pk>/", views.CancelPurchaseApproval.as_view(), name="cancel_purchase_aproval"),
    path("upload-purchase-attachment/<str:pk>/", views.UploadPurchaseAttachment.as_view(), name="upload_purchase_attachment"),
        path("delete-purchase-attachment/<str:pk>/", views.DeletePurchaseAttachment.as_view(), name="delete_purchase_attachment"),


    path("store/", views.StoreRequest.as_view(), name="store"),
    path("store/<str:pk>/", views.StoreDetails.as_view(), name="store_details"),
    path("store-approval/<str:pk>/", views.StoreApproval.as_view(), name="store_aproval"),
    path("cancel-store-approval/<str:pk>/", views.CancelStoreApproval.as_view(), name="cancel_store_aproval"),
    path("upload-store-attachment/<str:pk>/", views.UploadStoreAttachment.as_view(), name="upload_store_attachment"),
    path("delete-store-attachment/<str:pk>/", views.DeleteStoreAttachment.as_view(), name="delete_store_attachment"),
]