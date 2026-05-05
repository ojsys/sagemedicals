from django.urls import path

from surgery import views

app_name = "surgery"

urlpatterns = [
    path("", views.TheatreListView.as_view(), name="list"),
    path("book/", views.SurgeryBookingCreateView.as_view(), name="book"),
    path("<int:pk>/", views.SurgeryBookingDetailView.as_view(), name="detail"),
    path("<int:pk>/status/", views.SurgeryStatusUpdateView.as_view(), name="status"),
]
