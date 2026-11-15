from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    A single notification for one user. Created whenever something
    relevant happens to them (their proposal got accepted, someone
    applied to their job, etc.) — `link` is where clicking it takes them.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)  # e.g. "/jobs/3/proposals/"
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"To {self.recipient.username}: {self.message}"