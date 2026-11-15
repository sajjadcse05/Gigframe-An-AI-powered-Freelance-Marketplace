from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from .forms import ContactForm


class ContactView(TemplateView):
    """Public Contact page — no login required, so guests can also reach out."""
    template_name = "support/contact.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ContactForm()})

    def post(self, request):
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, self.template_name, {"form": ContactForm(), "submitted": True})
        return render(request, self.template_name, {"form": form})


class AboutView(TemplateView):
    """Static About page — no model needed."""
    template_name = "support/about.html"