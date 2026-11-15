from django.contrib import admin

from .models import Job, Proposal


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["title", "client", "category", "budget", "deadline", "is_open", "created_at"]
    list_filter = ["category", "is_open"]
    search_fields = ["title", "client__username"]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    """Powers the Admin Interface's dispute/oversight visibility into proposals."""
    list_display = ["job", "freelancer", "quoted_price", "status", "created_at"]
    list_filter = ["status"]