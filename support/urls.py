from django.urls import path
from .views import ContactView, AboutView

urlpatterns = [
    path("contact/", ContactView.as_view(), name="contact"),
    path("about/", AboutView.as_view(), name="about"),
]