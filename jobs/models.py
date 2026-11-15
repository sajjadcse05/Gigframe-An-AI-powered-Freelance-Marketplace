from django.conf import settings
from django.db import models


class Job(models.Model):
    """
    A Job = a request a Client posts ("I need a logo designed, budget
    ৳5000, deadline in 5 days"). Freelancers respond to Jobs with
    Proposals below.
    """

    CATEGORY_CHOICES = [
        ("Web Development", "Web Development"),
        ("Graphic Design", "Graphic Design"),
        ("Digital Marketing", "Digital Marketing"),
        ("Content Writing", "Content Writing"),
        ("Video Editing", "Video Editing"),
        ("Virtual Assistant", "Virtual Assistant"),
    ]

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    deadline = models.DateField()
    required_skills = models.CharField(
        max_length=300, blank=True,
        help_text="Comma-separated required skills, e.g. 'react, django'",
    )
    embedding = models.JSONField(null=True, blank=True, editable=False)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        from ai_engine.embeddings import get_embedding
        text = f"{self.title}. {self.description} Required skills: {self.required_skills}"
        self.embedding = get_embedding(text)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} — {self.client.username}"


class Proposal(models.Model):
    """A Freelancer's bid on a Job: cover letter, quoted price, delivery time."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="proposals")
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="proposals"
    )
    cover_letter = models.TextField()
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_days = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["job", "freelancer"]  # one proposal per freelancer per job

    def __str__(self):
        return f"Proposal by {self.freelancer.username} on {self.job.title}"