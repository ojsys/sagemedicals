from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("2fa/setup/", views.TwoFactorSetupView.as_view(), name="2fa_setup"),
    path("2fa/disable/", views.TwoFactorDisableView.as_view(), name="2fa_disable"),
    path("2fa/verify/", views.TwoFactorVerifyView.as_view(), name="2fa_verify"),

    # Staff management (Super Admin / Lead Doctor)
    path("users/", views.StaffUserListView.as_view(), name="user_list"),
    path("users/new/", views.StaffUserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/", views.StaffUserUpdateView.as_view(), name="user_edit"),
    path("users/<int:pk>/toggle-active/", views.StaffUserToggleActiveView.as_view(), name="user_toggle_active"),
    path("users/<int:pk>/toggle-lead/", views.StaffUserToggleLeadView.as_view(), name="user_toggle_lead"),
    path("users/<int:pk>/password/", views.StaffUserPasswordResetView.as_view(), name="user_password"),
]
