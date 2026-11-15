from django.urls import path

from .views import (
    DashboardView,
    UserListView, UserBanToggleView,
    VerificationListView, VerificationDecisionView,
    GigListView, GigToggleActiveView,
    JobListView, JobToggleOpenView,
    RevenueDashboardView, RevenueExportPDFView,
    ReviewListView, ReviewDeleteView,
    WithdrawalListView, WithdrawalDecisionView,
    SupportMessageListView, SupportMessageToggleResolvedView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="admin_dashboard"),
    path("users/", UserListView.as_view(), name="admin_user_list"),
    path("users/<int:pk>/toggle-ban/", UserBanToggleView.as_view(), name="admin_user_ban_toggle"),
    path("verification/", VerificationListView.as_view(), name="admin_verification_list"),
    path("verification/<int:pk>/decide/", VerificationDecisionView.as_view(), name="admin_verification_decide"),

    path("gigs/", GigListView.as_view(), name="admin_gig_list"),
    path("gigs/<int:pk>/toggle-active/", GigToggleActiveView.as_view(), name="admin_gig_toggle_active"),

    path("jobs/", JobListView.as_view(), name="admin_job_list"),
    path("jobs/<int:pk>/toggle-open/", JobToggleOpenView.as_view(), name="admin_job_toggle_open"),

    path("revenue/", RevenueDashboardView.as_view(), name="admin_revenue"),
    path("revenue/export/", RevenueExportPDFView.as_view(), name="admin_revenue_export"),

    path("reviews/", ReviewListView.as_view(), name="admin_review_list"),
    path("reviews/<int:pk>/delete/", ReviewDeleteView.as_view(), name="admin_review_delete"),

    path("withdrawals/", WithdrawalListView.as_view(), name="admin_withdrawal_list"),
    path("withdrawals/<int:pk>/decide/", WithdrawalDecisionView.as_view(), name="admin_withdrawal_decide"),

    path("support/", SupportMessageListView.as_view(), name="admin_support_list"),
    path("support/<int:pk>/toggle-resolved/", SupportMessageToggleResolvedView.as_view(), name="admin_support_toggle_resolved"),
]