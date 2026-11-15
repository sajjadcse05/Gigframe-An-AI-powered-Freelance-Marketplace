from django.contrib import admin

from .models import Contract, Review


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ["job", "client", "freelancer", "amount", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["transaction_id", "sslcommerz_val_id"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["reviewer", "reviewee", "rating", "created_at"]
    list_filter = ["rating"]