from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("bell/", views.NotificationBellView.as_view(), name="bell"),
    path("count/", views.NotificationCountView.as_view(), name="count"),
]
