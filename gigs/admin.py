from django.contrib import admin

from .models import Gig, GigImage


class GigImageInline(admin.TabularInline):
    model = GigImage
    extra = 1


@admin.register(Gig)
class GigAdmin(admin.ModelAdmin):
    """Powers the Admin Interface's 'Gig/job moderation queue'."""
    list_display = ["title", "freelancer", "category", "price", "is_active", "created_at"]
    list_filter = ["category", "is_active"]
    search_fields = ["title", "freelancer__username"]
    actions = ["deactivate_gigs"]
    inlines = [GigImageInline]

    @admin.action(description="Deactivate selected gigs (remove from marketplace)")
    def deactivate_gigs(self, request, queryset):
        queryset.update(is_active=False)