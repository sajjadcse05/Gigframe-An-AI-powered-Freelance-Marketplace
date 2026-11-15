from django import forms
from .models import Message


class MessageForm(forms.ModelForm):
    # Make text optional so users can send standalone file attachments
    text = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Type a message...", "autocomplete": "off"}
        ),
    )

    class Meta:
        model = Message
        fields = ["text", "file"]

    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get("text")
        file = cleaned_data.get("file")

        # Prevent sending empty submissions (no text AND no file attached)
        if not text and not file:
            raise forms.ValidationError("Cannot send an empty message.")

        return cleaned_data