from django import forms
from django.contrib.auth.forms import UserCreationForm

from gigs.models import Gig
from .models import User, WorkExperience, Education, Certification


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=[(User.Role.FREELANCER, "Freelancer — I want to offer services"),
                 (User.Role.CLIENT, "Client — I want to hire freelancers")],
        widget=forms.RadioSelect,
    )

    class Meta:
        model = User
        fields = ["username", "email", "role", "password1", "password2"]

    def clean_email(self):
        """
        Django calls clean_<fieldname>() automatically for extra
        validation. Here we reject registration if the email is
        already used by another account — Django's default User
        model allows duplicate emails unless you explicitly check,
        which is exactly the gap you found.
        """
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ProfileForm(forms.ModelForm):
    """Freelancer profile. Skills = the same six categories the site has."""

    skills_select = forms.MultipleChoiceField(
        choices=Gig.CATEGORY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Skills",
    )

    class Meta:
        model = User
        fields = ["bio", "hourly_rate", "avatar", "cv"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 5, "placeholder": "Tell about yourself..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.skills:
            self.fields["skills_select"].initial = [
                s.strip() for s in self.instance.skills.split(",") if s.strip()
            ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.skills = ", ".join(self.cleaned_data.get("skills_select", []))
        if commit:
            user.save()
        return user


class ClientProfileForm(forms.ModelForm):
    """Client profile: photo, bio, and which freelancer categories they need."""

    needed_categories_select = forms.MultipleChoiceField(
        choices=Gig.CATEGORY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Which type of freelancer do you need?",
    )

    class Meta:
        model = User
        fields = ["bio", "avatar"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 5, "placeholder": "Tell about yourself..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.needed_categories:
            self.fields["needed_categories_select"].initial = [
                c.strip() for c in self.instance.needed_categories.split(",") if c.strip()
            ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.needed_categories = ", ".join(self.cleaned_data.get("needed_categories_select", []))
        if commit:
            user.save()
        return user


class NIDVerificationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["nid_number", "nid_document"]

    def clean_nid_number(self):
        """
        Bangladesh NID numbers are 10, 13, or 17 digits depending on
        when they were issued (old vs. new smart NID system). We
        accept any of those three lengths, digits only.
        """
        nid = self.cleaned_data["nid_number"].strip()
        if not nid.isdigit() or len(nid) not in [10, 13, 17]:
            raise forms.ValidationError("Enter a valid NID number (10, 13, or 17 digits).")

        # The model's unique=True already enforces this at the database
        # level, but checking here first gives a friendlier error message
        # instead of a raw database error, and excludes the current user
        # so re-submitting your OWN existing number doesn't falsely fail.
        existing = User.objects.filter(nid_number=nid).exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This NID number is already registered to another account.")

        return nid


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = ["title", "company_name", "employment_type", "start_date", "end_date", "currently_working", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4, "maxlength": 2000}),
        }


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ["school", "degree", "field_of_study", "graduation_year"]


class CertificationForm(forms.ModelForm):
    class Meta:
        model = Certification
        fields = ["name", "issuing_organization", "year_received", "certificate_image"]