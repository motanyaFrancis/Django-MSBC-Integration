from django.urls import path
from accounts import views

urlpatterns = [
    path("auth/", views.LoginView.as_view(), name="auth"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path('reset-password/', views.ResetPasswordView.as_view(), name='reset_password'),
    path('reset/', views.ResetPasswordView.as_view(), name='reset'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('change-password/', views.ChangePortalPasswordView.as_view(), name='change_password'),

]
