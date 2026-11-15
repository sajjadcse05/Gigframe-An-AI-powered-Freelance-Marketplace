from django import forms

from .models import Gig


class GigForm(forms.ModelForm):
    class Meta:
        model = Gig
        fields = ["title", "description", "category", "price", "delivery_days", "tags", "video"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }


class GigOrderForm(forms.Form):
    """
    Lets a Client hire a Gig's freelancer directly with a custom
    budget, instead of going through the Job → Proposal → Accept
    flow manually. Not tied to a model, since it doesn't map onto
    any single table — submitting it creates a Job, an auto-accepted
    Proposal, and a Contract all at once.
    """
    amount = forms.DecimalField(
        label="Your budget (৳)",
        min_value=1,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"min": "1", "step": "0.01", "placeholder": "e.g. 5000"}),
    )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount