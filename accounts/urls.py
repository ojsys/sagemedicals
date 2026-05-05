from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("2fa/setup/", views.TwoFactorSetupView.as_view(), name="2fa_setup"),
    path("2fa/disable/", views.TwoFactorDisableView.as_view(), name="2fa_disable"),
    path("2fa/verify/", views.TwoFactorVerifyView.as_view(), name="2fa_verify"),
]
