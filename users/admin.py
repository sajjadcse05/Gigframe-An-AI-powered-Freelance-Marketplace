from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Extends Django's built-in UserAdmin and adds our custom fields
    (role, verification status) — this IS most of the Admin Interface's
    "User management" requirement, with almost no custom code.
    """

    list_display = ["username", "email", "role", "verification_status", "is_verified", "is_active", "date_joined"]
    list_filter = ["role", "verification_status", "is_verified", "is_active"]
    search_fields = ["username", "email", "nid_number"]
    actions = ["approve_verification", "reject_verification", "ban_users"]
    readonly_fields = ["nid_document_preview"]

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Gigframe Profile", {"fields": ("role", "bio", "skills", "hourly_rate", "avatar", "email_verified")}),
        ("NID Identity Verification", {
            "fields": ("nid_number", "nid_document_preview", "verification_status", "is_verified", "verification_rejection_reason"),
        }),
    )

    def nid_document_preview(self, obj):
        """
        Shows the actual uploaded NID photo directly inside the admin
        edit page, so you can review it without downloading the file
        separately — this is the core of the manual review workflow.
        """
        if obj.nid_document:
            return format_html('<img src="{}" style="max-width: 400px; border-radius: 8px;" />', obj.nid_document.url)
        return "No document submitted"
    nid_document_preview.short_description = "NID Document"

    @admin.action(description="Approve selected verification submissions")
    def approve_verification(self, request, queryset):
        updated = queryset.filter(verification_status=User.VerificationStatus.PENDING).update(
            verification_status=User.VerificationStatus.APPROVED,
            is_verified=True,
        )
        self.message_user(request, f"{updated} user(s) approved and verified.")

    @admin.action(description="Reject selected verification submissions")
    def reject_verification(self, request, queryset):
        updated = queryset.filter(verification_status=User.VerificationStatus.PENDING).update(
            verification_status=User.VerificationStatus.REJECTED,
            is_verified=False,
        )
        self.message_user(request, f"{updated} user(s) rejected. You can add a rejection_reason by editing them individually.")

    @admin.action(description="Ban (deactivate) selected users")
    def ban_users(self, request, queryset):
        queryset.update(is_active=False)