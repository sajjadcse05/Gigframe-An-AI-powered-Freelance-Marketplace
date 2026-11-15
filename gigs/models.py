from django.conf import settings
from django.db import models


class Gig(models.Model):
    """
    A Gig = a service a Freelancer offers, Fiverr-style
    ("I will build you a website for ৳5000").
    """

    CATEGORY_CHOICES = [
        ("Web Development", "Web Development"),
        ("Graphic Design", "Graphic Design"),
        ("Digital Marketing", "Digital Marketing"),
        ("Content Writing", "Content Writing"),
        ("Video Editing", "Video Editing"),
        ("Virtual Assistant", "Virtual Assistant"),
    ]

    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gigs"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_days = models.PositiveIntegerField(help_text="Delivery time in days")
    tags = models.CharField(
        max_length=300, blank=True,
        help_text="Comma-separated tags, e.g. 'react, django, fullstack'",
    )
    video = models.FileField(upload_to="gig_videos/", blank=True, null=True)
    embedding = models.JSONField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        from ai_engine.embeddings import get_embedding
        # Recompute the embedding every time the gig is saved, from its
        # title + description + tags — this is the text the AI matching
        # engine actually compares against job postings.
        text = f"{self.title}. {self.description} Tags: {self.tags}"
        self.embedding = get_embedding(text)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} — {self.freelancer.username}"


class GigImage(models.Model):
    """
    A single image belonging to a Gig. Separate model (not a field on
    Gig) because Fiverr-style listings support MULTIPLE images per gig
    — one ForeignKey row per uploaded image.
    """

    gig = models.ForeignKey(Gig, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="gig_images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.gig.title}"