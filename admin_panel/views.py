from datetime import timedelta, datetime
from io import BytesIO

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, Avg
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from gigs.models import Gig
from jobs.models import Job
from contracts.models import Contract, Review, WithdrawalRequest
from notifications.models import Notification
from support.models import ContactMessage
from .mixins import AdminRequiredMixin

User = get_user_model()

RANGE_DAYS = {"7": 7, "15": 15, "30": 30, "90": 90}


class DashboardView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["total_freelancers"] = User.objects.filter(role="FREELANCER").count()
        context["total_clients"] = User.objects.filter(role="CLIENT").count()
        context["pending_verifications"] = User.objects.filter(verification_status="PENDING").count()

        context["total_gigs"] = Gig.objects.count()
        context["active_gigs"] = Gig.objects.filter(is_active=True).count()

        context["total_jobs"] = Job.objects.count()
        context["open_jobs"] = Job.objects.filter(is_open=True).count()

        context["total_contracts"] = Contract.objects.count()
        context["completed_contracts"] = Contract.objects.filter(status="COMPLETED").count()

        revenue = Contract.objects.filter(status="COMPLETED").aggregate(total=Sum("amount"))
        context["total_revenue"] = revenue["total"] or 0

        context["pending_withdrawals"] = WithdrawalRequest.objects.filter(
            status=WithdrawalRequest.Status.PENDING
        ).count()

        context["open_support_messages"] = ContactMessage.objects.filter(is_resolved=False).count()

        context["recent_users"] = User.objects.exclude(role="ADMIN").order_by("-date_joined")[:5]
        context["recent_gigs"] = Gig.objects.order_by("-created_at")[:5]

        return context


class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "admin_panel/user_list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.exclude(role="ADMIN").order_by("-date_joined")
        role = self.request.GET.get("role")
        if role in ("FREELANCER", "CLIENT"):
            qs = qs.filter(role=role)
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_role"] = self.request.GET.get("role", "")
        context["search_query"] = self.request.GET.get("q", "")
        return context


class UserBanToggleView(AdminRequiredMixin, View):
    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        return redirect("admin_user_list")


class VerificationListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "admin_panel/verification_list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        status = self.request.GET.get("status", "PENDING")
        qs = User.objects.exclude(role="ADMIN").exclude(verification_status="NOT_SUBMITTED")
        if status in ("PENDING", "APPROVED", "REJECTED"):
            qs = qs.filter(verification_status=status)
        return qs.order_by("-date_joined")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_status"] = self.request.GET.get("status", "PENDING")
        return context


class VerificationDecisionView(AdminRequiredMixin, View):
    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        decision = request.POST.get("decision")

        if decision == "approve":
            target.verification_status = User.VerificationStatus.APPROVED
            target.is_verified = True
            target.verification_rejection_reason = ""
        elif decision == "reject":
            target.verification_status = User.VerificationStatus.REJECTED
            target.is_verified = False
            target.verification_rejection_reason = request.POST.get("reason", "").strip()

        target.save(update_fields=["verification_status", "is_verified", "verification_rejection_reason"])
        return redirect("admin_verification_list")


class GigListView(AdminRequiredMixin, ListView):
    model = Gig
    template_name = "admin_panel/gig_list.html"
    context_object_name = "gigs"
    paginate_by = 20

    def get_queryset(self):
        qs = Gig.objects.select_related("freelancer").order_by("-created_at")
        category = self.request.GET.get("category")
        if category:
            qs = qs.filter(category=category)
        status = self.request.GET.get("status")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(freelancer__username__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_category"] = self.request.GET.get("category", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("q", "")
        context["categories"] = Gig.CATEGORY_CHOICES
        return context


class GigToggleActiveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        gig = get_object_or_404(Gig, pk=pk)
        gig.is_active = not gig.is_active
        gig.save(update_fields=["is_active"])
        return redirect("admin_gig_list")


class JobListView(AdminRequiredMixin, ListView):
    model = Job
    template_name = "admin_panel/job_list.html"
    context_object_name = "jobs"
    paginate_by = 20

    def get_queryset(self):
        qs = Job.objects.select_related("client").order_by("-created_at")
        category = self.request.GET.get("category")
        if category:
            qs = qs.filter(category=category)
        status = self.request.GET.get("status")
        if status == "open":
            qs = qs.filter(is_open=True)
        elif status == "closed":
            qs = qs.filter(is_open=False)
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(client__username__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_category"] = self.request.GET.get("category", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("q", "")
        context["categories"] = Job.CATEGORY_CHOICES
        return context


class JobToggleOpenView(AdminRequiredMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)
        job.is_open = not job.is_open
        job.save(update_fields=["is_open"])
        return redirect("admin_job_list")


def _resolve_date_range(request):
    range_key = request.GET.get("range", "all")
    now = timezone.now()

    if range_key in RANGE_DAYS:
        return range_key, now - timedelta(days=RANGE_DAYS[range_key]), now, f"Last {RANGE_DAYS[range_key]} days"

    if range_key == "custom":
        start_str = request.GET.get("start", "")
        end_str = request.GET.get("end", "")
        try:
            date_from = timezone.make_aware(datetime.strptime(start_str, "%Y-%m-%d"))
            date_to = timezone.make_aware(datetime.strptime(end_str, "%Y-%m-%d")) + timedelta(days=1)
            return "custom", date_from, date_to, f"{start_str} to {end_str}"
        except ValueError:
            return "all", None, None, "All time"

    return "all", None, None, "All time"


def _build_revenue_context(request):
    range_key, date_from, date_to, range_label = _resolve_date_range(request)

    completed = Contract.objects.filter(status=Contract.Status.COMPLETED)
    if date_from and date_to:
        completed = completed.filter(completed_at__gte=date_from, completed_at__lt=date_to)

    total_revenue = completed.aggregate(total=Sum("amount"))["total"] or 0
    commission_percent = Contract.PLATFORM_COMMISSION_PERCENT
    platform_earnings = round(total_revenue * commission_percent / 100, 2)
    freelancer_payouts = total_revenue - platform_earnings

    status_counts = Contract.objects.values("status").annotate(count=Count("id")).order_by("status")

    by_category = []
    for row in (
        completed.values("job__category")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    ):
        row = dict(row)
        row["platform_earnings"] = round(row["total"] * commission_percent / 100, 2)
        by_category.append(row)

    top_freelancers = (
        completed.values("freelancer__username")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")[:10]
    )

    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_revenue = (
        Contract.objects.filter(status=Contract.Status.COMPLETED, completed_at__gte=six_months_ago)
        .extra(select={"month": "strftime('%%Y-%%m', completed_at)"})
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    recent_transactions = completed.select_related("job", "client", "freelancer").order_by("-completed_at")[:20]

    return {
        "range_key": range_key,
        "range_label": range_label,
        "custom_start": request.GET.get("start", ""),
        "custom_end": request.GET.get("end", ""),
        "total_revenue": total_revenue,
        "completed_count": completed.count(),
        "commission_percent": commission_percent,
        "platform_earnings": platform_earnings,
        "freelancer_payouts": freelancer_payouts,
        "status_counts": status_counts,
        "by_category": by_category,
        "top_freelancers": top_freelancers,
        "monthly_revenue": monthly_revenue,
        "recent_transactions": recent_transactions,
    }


class RevenueDashboardView(AdminRequiredMixin, TemplateView):
    template_name = "admin_panel/revenue.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_build_revenue_context(self.request))
        return context


class RevenueExportPDFView(AdminRequiredMixin, View):
    def get(self, request):
        context = _build_revenue_context(request)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Gigframe Revenue Report")
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("Gigframe — Revenue Report", styles["Title"]))
        elements.append(Paragraph(f"Period: {context['range_label']}", styles["Normal"]))
        elements.append(Paragraph(f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        elements.append(Spacer(1, 16))

        summary_data = [
            ["Metric", "Amount"],
            ["Total Transaction Volume", f"BDT {context['total_revenue']}"],
            [f"Platform Earnings ({context['commission_percent']}%)", f"BDT {context['platform_earnings']}"],
            ["Freelancer Payouts", f"BDT {context['freelancer_payouts']}"],
            ["Completed Contracts", str(context["completed_count"])],
        ]
        summary_table = Table(summary_data, colWidths=[260, 180])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0e3b36")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("Platform Earnings by Category", styles["Heading2"]))
        cat_data = [["Category", "Contracts", "Revenue", f"Platform Earnings ({context['commission_percent']}%)"]]
        for c in context["by_category"]:
            cat_data.append([
                c["job__category"] or "—", str(c["count"]),
                f"BDT {c['total']}", f"BDT {c['platform_earnings']}",
            ])
        if len(cat_data) == 1:
            cat_data.append(["No data", "-", "-", "-"])
        cat_table = Table(cat_data, colWidths=[140, 70, 100, 150])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf3f2")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elements.append(cat_table)
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("Top Earning Freelancers", styles["Heading2"]))
        fl_data = [["Freelancer", "Contracts", "Earned"]]
        for f in context["top_freelancers"]:
            fl_data.append([f["freelancer__username"], str(f["count"]), f"BDT {f['total']}"])
        if len(fl_data) == 1:
            fl_data.append(["No data", "-", "-"])
        fl_table = Table(fl_data, colWidths=[200, 90, 100])
        fl_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf3f2")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elements.append(fl_table)

        doc.build(elements)
        buffer.seek(0)

        filename = f"gigframe-revenue-{context['range_key']}-{timezone.now().strftime('%Y%m%d')}.pdf"
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ReviewListView(AdminRequiredMixin, ListView):
    model = Review
    template_name = "admin_panel/review_list.html"
    context_object_name = "reviews"
    paginate_by = 20

    def get_queryset(self):
        qs = Review.objects.select_related("reviewer", "reviewee", "contract__job").order_by("-created_at")
        rating = self.request.GET.get("rating")
        if rating in ("1", "2", "3", "4", "5"):
            qs = qs.filter(rating=rating)
        search = self.request.GET.get("q")
        if search:
            qs = qs.filter(
                Q(reviewer__username__icontains=search)
                | Q(reviewee__username__icontains=search)
                | Q(comment__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_rating"] = self.request.GET.get("rating", "")
        context["search_query"] = self.request.GET.get("q", "")
        context["avg_rating"] = Review.objects.aggregate(avg=Avg("rating"))["avg"] or 0
        return context


class ReviewDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        review.delete()
        return redirect("admin_review_list")


class WithdrawalListView(AdminRequiredMixin, ListView):
    model = WithdrawalRequest
    template_name = "admin_panel/withdrawal_list.html"
    context_object_name = "withdrawals"
    paginate_by = 20

    def get_queryset(self):
        status = self.request.GET.get("status", "PENDING")
        qs = WithdrawalRequest.objects.select_related("freelancer").order_by("-requested_at")
        if status in ("PENDING", "APPROVED", "REJECTED"):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_status"] = self.request.GET.get("status", "PENDING")
        return context


class WithdrawalDecisionView(AdminRequiredMixin, View):
    def post(self, request, pk):
        withdrawal = get_object_or_404(WithdrawalRequest, pk=pk, status=WithdrawalRequest.Status.PENDING)
        decision = request.POST.get("decision")

        if decision == "approve":
            withdrawal.status = WithdrawalRequest.Status.APPROVED
            withdrawal.processed_at = timezone.now()
            withdrawal.save()
            Notification.objects.create(
                recipient=withdrawal.freelancer,
                message=f"Your withdrawal of ৳{withdrawal.amount} was approved and sent.",
                link="/contracts/earnings/",
            )
        elif decision == "reject":
            withdrawal.status = WithdrawalRequest.Status.REJECTED
            withdrawal.admin_note = request.POST.get("reason", "").strip()
            withdrawal.processed_at = timezone.now()
            withdrawal.save()
            Notification.objects.create(
                recipient=withdrawal.freelancer,
                message=f"Your withdrawal request of ৳{withdrawal.amount} was rejected.",
                link="/contracts/earnings/",
            )

        return redirect("admin_withdrawal_list")


class SupportMessageListView(AdminRequiredMixin, ListView):
    """
    Support inbox — every Contact form submission, filterable by
    resolved status. Mirrors the same list-view pattern used for
    Users, Gigs, and Jobs elsewhere in the Admin Panel.
    """
    model = ContactMessage
    template_name = "admin_panel/support_list.html"
    context_object_name = "messages_list"
    paginate_by = 20

    def get_queryset(self):
        status = self.request.GET.get("status", "open")
        qs = ContactMessage.objects.all()
        if status == "open":
            qs = qs.filter(is_resolved=False)
        elif status == "resolved":
            qs = qs.filter(is_resolved=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_status"] = self.request.GET.get("status", "open")
        return context


class SupportMessageToggleResolvedView(AdminRequiredMixin, View):
    def post(self, request, pk):
        message = get_object_or_404(ContactMessage, pk=pk)
        message.is_resolved = not message.is_resolved
        message.save(update_fields=["is_resolved"])
        return redirect("admin_support_list")