from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        FREELANCER = "FREELANCER", "Freelancer"
        CLIENT = "CLIENT", "Client"
        ADMIN = "ADMIN", "Admin"

    class VerificationStatus(models.TextChoices):
        NOT_SUBMITTED = "NOT_SUBMITTED", "Not Submitted"
        PENDING = "PENDING", "Pending Review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)

    bio = models.TextField(blank=True)
    skills = models.CharField(
        max_length=500, blank=True,
        help_text="Comma-separated skills, e.g. 'React, Django, UI Design'",
    )
    needed_categories = models.CharField(   # <- ADDED: categories a client wants to hire for
        max_length=300, blank=True,
        help_text="Comma-separated freelancer categories a client wants to hire for",
    )
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    cv = models.FileField(upload_to="cvs/", blank=True, null=True)
    embedding = models.JSONField(null=True, blank=True, editable=False)   # <- ADDED: AI semantic vector from bio+skills, recomputed on save
    is_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    # NID identity verification
    nid_number = models.CharField(
        max_length=17, blank=True, null=True, unique=True,
        help_text="Bangladesh NID number — must be unique across all accounts",
    )
    nid_document = models.ImageField(upload_to="nid_documents/", blank=True, null=True)
    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.NOT_SUBMITTED
    )
    verification_rejection_reason = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):   # <- ADDED (whole method)
        from ai_engine.embeddings import get_embedding
        # Only Freelancers have anything meaningful to match against —
        # Clients don't post skills/bio for the AI matching engine to use.
        if self.role == self.Role.FREELANCER:
            text = f"{self.bio} Skills: {self.skills}"
            self.embedding = get_embedding(text)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"


class WorkExperience(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full-time"
        PART_TIME = "PART_TIME", "Part-time"
        FREELANCE = "FREELANCE", "Freelance"
        INTERNSHIP = "INTERNSHIP", "Internship"
        CONTRACT = "CONTRACT", "Contract"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_experiences")
    title = models.CharField(max_length=150)
    company_name = models.CharField(max_length=150)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_working = models.BooleanField(default=False)
    description = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.title} at {self.company_name}"


class Education(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="education_entries")
    school = models.CharField(max_length=150)
    degree = models.CharField(max_length=100, blank=True)
    field_of_study = models.CharField(max_length=150, blank=True)
    graduation_year = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-graduation_year"]

    def __str__(self):
        return f"{self.degree} — {self.school}"


class Certification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certifications")
    name = models.CharField(max_length=150)
    issuing_organization = models.CharField(max_length=150, blank=True)
    year_received = models.PositiveIntegerField(null=True, blank=True)
    certificate_image = models.ImageField(upload_to="certifications/", blank=True, null=True)

    class Meta:
        ordering = ["-year_received"]

    def __str__(self):
        return f"{self.name} ({self.issuing_organization})"