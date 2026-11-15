from django.db import models


class ContactMessage(models.Model):
    """
    A message submitted through the public Contact page. Stores the
    submitter's username and email as plain text rather than a User
    FK, since anyone — including a logged-out visitor — should be
    able to reach out for help without needing an account.
    """
    username = models.CharField(max_length=150)
    email = models.EmailField()
    problem = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} ({self.email}) — {'Resolved' if self.is_resolved else 'Open'}"