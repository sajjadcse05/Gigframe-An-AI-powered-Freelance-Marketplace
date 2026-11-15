from django import forms
from django.utils import timezone

from .models import Job, Proposal


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ["title", "description", "category", "budget", "deadline", "required_skills"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "budget": forms.NumberInput(attrs={"min": "1", "step": "0.01"}),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline < timezone.localdate():
            raise forms.ValidationError("Deadline can't be in the past.")
        return deadline

    def clean_budget(self):
        budget = self.cleaned_data["budget"]
        if budget <= 0:
            raise forms.ValidationError("Budget must be greater than zero.")
        return budget


class ProposalForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = ["cover_letter", "quoted_price", "delivery_days"]
        widgets = {
            "cover_letter": forms.Textarea(attrs={"rows": 5}),
            "quoted_price": forms.NumberInput(attrs={"min": "1", "step": "0.01"}),
            "delivery_days": forms.NumberInput(attrs={"min": "1"}),
        }

    def clean_quoted_price(self):
        quoted_price = self.cleaned_data["quoted_price"]
        if quoted_price <= 0:
            raise forms.ValidationError("Your price must be greater than zero.")
        return quoted_price

    def clean_delivery_days(self):
        delivery_days = self.cleaned_data["delivery_days"]
        if delivery_days <= 0:
            raise forms.ValidationError("Delivery days must be at least 1.")
        return delivery_days