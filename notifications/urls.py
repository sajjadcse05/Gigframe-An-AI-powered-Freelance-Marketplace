from django.urls import path

from .views import notification_list, mark_read_and_redirect

urlpatterns = [
    path("", notification_list, name="notification_list"),
    path("<int:pk>/read/", mark_read_and_redirect, name="mark_notification_read"),
]