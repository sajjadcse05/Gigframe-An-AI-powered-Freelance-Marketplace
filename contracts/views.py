import io
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from notifications.models import Notification
from .models import Contract, Review, WithdrawalRequest
from .forms import ReviewForm
from .sslcommerz import initiate_payment, validate_payment, initiate_refund


@login_required
def contract_detail(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    if request.user not in [contract.client, contract.freelancer]:
        raise PermissionDenied("You're not part of this contract.")

    if contract.cancellation_pending and contract.cancellation_deadline_passed:
        _finalize_cancellation(contract)

    already_reviewed = contract.reviews.filter(reviewer=request.user).exists()

    return render(request, "contracts/contract_detail.html", {
        "contract": contract,
        "already_reviewed": already_reviewed,
    })


@login_required
def client_contracts(request):
    contracts = Contract.objects.filter(client=request.user).select_related("job", "freelancer").order_by("-created_at")
    return render(request, "contracts/client_contracts.html", {"contracts": contracts})


@login_required
def start_payment(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    if request.user != contract.client:
        raise PermissionDenied("Only the client can fund this contract.")

    gateway_url = initiate_payment(contract, request)
    if gateway_url:
        return redirect(gateway_url)

    return render(request, "contracts/payment_error.html", {"contract": contract})


@csrf_exempt
@require_POST
def payment_success(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    val_id = request.POST.get("val_id")

    validation_data = validate_payment(val_id) if val_id else None

    if validation_data:
        contract.status = Contract.Status.FUNDED
        contract.transaction_id = request.POST.get("tran_id", "")
        contract.sslcommerz_val_id = val_id
        contract.bank_tran_id = validation_data.get("bank_tran_id", "")
        contract.funded_at = timezone.now()
        contract.save()

        Notification.objects.create(
            recipient=contract.freelancer,
            message=f"Payment received for \"{contract.job.title}\" — you can start work.",
            link=f"/contracts/{contract.pk}/",
        )
        return redirect("contract_detail", pk=contract.pk)

    return render(request, "contracts/payment_error.html", {"contract": contract})


@csrf_exempt
@require_POST
def payment_fail(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    return render(request, "contracts/payment_error.html", {"contract": contract, "reason": "failed"})


@csrf_exempt
@require_POST
def payment_cancel(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    return render(request, "contracts/payment_error.html", {"contract": contract, "reason": "cancelled"})


@login_required
def mark_delivered(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    if request.user != contract.freelancer:
        raise PermissionDenied("Only the freelancer can mark this as delivered.")

    if contract.status == Contract.Status.FUNDED:
        contract.status = Contract.Status.DELIVERED
        contract.delivered_at = timezone.now()
        contract.save()

        Notification.objects.create(
            recipient=contract.client,
            message=f"\"{contract.job.title}\" has been marked as delivered — please review.",
            link=f"/contracts/{contract.pk}/",
        )

    return redirect("contract_detail", pk=contract.pk)


@login_required
def approve_and_release(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    if request.user != contract.client:
        raise PermissionDenied("Only the client can approve and release payment.")

    if contract.status == Contract.Status.DELIVERED:
        contract.status = Contract.Status.COMPLETED
        contract.completed_at = timezone.now()
        contract.save()

        Notification.objects.create(
            recipient=contract.freelancer,
            message=f"Payment released for \"{contract.job.title}\" — contract completed!",
            link=f"/contracts/{contract.pk}/",
        )

    return redirect("contract_detail", pk=contract.pk)


@login_required
def request_cancellation(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    if request.user not in [contract.client, contract.freelancer]:
        raise PermissionDenied("You're not part of this contract.")

    if contract.status not in (Contract.Status.FUNDED, Contract.Status.DELIVERED):
        raise PermissionDenied("This contract can't be cancelled from its current status.")

    if contract.cancellation_pending:
        raise PermissionDenied("A cancellation request is already pending on this contract.")

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        contract.cancellation_requested_by = request.user
        contract.cancellation_reason = reason
        contract.cancellation_requested_at = timezone.now()
        contract.save()

        other_party = contract.freelancer if request.user == contract.client else contract.client
        Notification.objects.create(
            recipient=other_party,
            message=f"{request.user.username} requested to cancel \"{contract.job.title}\" — respond within 48 hours.",
            link=f"/contracts/{contract.pk}/",
        )
        return redirect("contract_detail", pk=contract.pk)

    return render(request, "contracts/request_cancellation.html", {"contract": contract})


@login_required
def respond_to_cancellation(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    if request.user not in [contract.client, contract.freelancer]:
        raise PermissionDenied("You're not part of this contract.")

    if not contract.cancellation_pending:
        raise PermissionDenied("There's no pending cancellation request on this contract.")

    if request.user == contract.cancellation_requested_by:
        raise PermissionDenied("You can't respond to your own cancellation request.")

    decision = request.POST.get("decision")

    if decision == "accept":
        _finalize_cancellation(contract)
    elif decision == "decline":
        contract.cancellation_requested_by = None
        contract.cancellation_reason = ""
        contract.cancellation_requested_at = None
        contract.save()

        Notification.objects.create(
            recipient=contract.client if request.user == contract.freelancer else contract.freelancer,
            message=f"Your cancellation request for \"{contract.job.title}\" was declined.",
            link=f"/contracts/{contract.pk}/",
        )

    return redirect("contract_detail", pk=contract.pk)


def _finalize_cancellation(contract):
    refund_ref_id = initiate_refund(contract)

    contract.status = Contract.Status.CANCELLED
    contract.refund_ref_id = refund_ref_id or ""
    contract.cancelled_at = timezone.now()
    contract.save()

    Notification.objects.create(
        recipient=contract.client,
        message=f"\"{contract.job.title}\" was cancelled — your ৳{contract.amount} refund has been initiated.",
        link=f"/contracts/{contract.pk}/",
    )
    Notification.objects.create(
        recipient=contract.freelancer,
        message=f"\"{contract.job.title}\" has been cancelled.",
        link=f"/contracts/{contract.pk}/",
    )


@login_required
def leave_review(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    if request.user not in [contract.client, contract.freelancer]:
        raise PermissionDenied("You're not part of this contract.")

    if contract.status != Contract.Status.COMPLETED:
        raise PermissionDenied("You can only review a completed contract.")

    reviewee = contract.freelancer if request.user == contract.client else contract.client

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.contract = contract
            review.reviewer = request.user
            review.reviewee = reviewee
            review.save()

            Notification.objects.create(
                recipient=reviewee,
                message=f"{request.user.username} left you a {review.rating}★ review",
                link=f"/auth/profile/{reviewee.username}/",
            )
            return redirect("contract_detail", pk=contract.pk)
    else:
        form = ReviewForm()

    return render(request, "contracts/leave_review.html", {"contract": contract, "reviewee": reviewee, "form": form})


# ---------------------------------------------------------------------------
# Earnings — pending vs withdrawable balance, filterable by date range
# ---------------------------------------------------------------------------

def _parse_earnings_range(request):
    today = timezone.localdate()
    default_start = today - timedelta(days=30)
    clamped = False

    def _parse(raw_value, fallback):
        nonlocal clamped
        try:
            parsed = datetime.strptime(raw_value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return fallback
        if parsed > today:
            clamped = True
            return today
        return parsed

    start_date = _parse(request.GET.get("start_date", ""), default_start)
    end_date = _parse(request.GET.get("end_date", ""), today)

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date, clamped


def _earnings_data(user, start_date, end_date):
    pending_qs = Contract.objects.filter(
        freelancer=user,
        status__in=[Contract.Status.FUNDED, Contract.Status.DELIVERED],
        funded_at__date__gte=start_date,
        funded_at__date__lte=end_date,
    ).select_related("job", "client").order_by("-funded_at")

    withdrawable_qs = Contract.objects.filter(
        freelancer=user,
        status=Contract.Status.COMPLETED,
        completed_at__date__gte=start_date,
        completed_at__date__lte=end_date,
    ).select_related("job", "client").order_by("-completed_at")

    pending_total = sum((c.freelancer_payout for c in pending_qs), Decimal("0.00"))
    withdrawable_total = sum((c.freelancer_payout for c in withdrawable_qs), Decimal("0.00"))

    return pending_qs, withdrawable_qs, pending_total, withdrawable_total


def _current_withdrawable_balance(user):
    """
    All-time balance available to withdraw right now — NOT limited to
    the earnings page's date-range filter. This is:
      (all-time COMPLETED contract payouts)
      minus (amounts already PENDING or APPROVED in withdrawal requests)
    so a freelancer can't request more than they actually have, and
    can't double-request the same money while one request is pending.
    """
    completed_contracts = Contract.objects.filter(freelancer=user, status=Contract.Status.COMPLETED)
    total_completed = sum((c.freelancer_payout for c in completed_contracts), Decimal("0.00"))

    reserved = WithdrawalRequest.objects.filter(
        freelancer=user, status__in=[WithdrawalRequest.Status.PENDING, WithdrawalRequest.Status.APPROVED]
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    return total_completed - reserved


@login_required
def freelancer_earnings(request):
    start_date, end_date, clamped = _parse_earnings_range(request)
    pending_qs, withdrawable_qs, pending_total, withdrawable_total = _earnings_data(
        request.user, start_date, end_date
    )
    current_balance = _current_withdrawable_balance(request.user)
    my_withdrawals = WithdrawalRequest.objects.filter(freelancer=request.user)[:10]

    return render(request, "contracts/earnings.html", {
        "start_date": start_date,
        "end_date": end_date,
        "today": timezone.localdate(),
        "date_range_clamped": clamped,
        "pending_contracts": pending_qs,
        "withdrawable_contracts": withdrawable_qs,
        "pending_total": pending_total,
        "withdrawable_total": withdrawable_total,
        "current_balance": current_balance,
        "my_withdrawals": my_withdrawals,
    })


@login_required
@require_POST
def request_withdrawal(request):
    amount_raw = request.POST.get("amount", "").strip()
    method = request.POST.get("method", "").strip()
    bank_name = request.POST.get("bank_name", "").strip()
    account_number = request.POST.get("account_number", "").strip()
    account_holder_name = request.POST.get("account_holder_name", "").strip()

    errors = []

    try:
        amount = Decimal(amount_raw)
    except Exception:
        amount = None
        errors.append("Enter a valid amount.")

    if amount is not None and amount <= 0:
        errors.append("Amount must be greater than zero.")

    current_balance = _current_withdrawable_balance(request.user)
    if amount is not None and amount > current_balance:
        errors.append(f"You can't withdraw more than your available balance (৳{current_balance}).")

    if method not in WithdrawalRequest.Method.values:
        errors.append("Select a valid withdrawal method.")

    if not account_holder_name:
        errors.append("Account holder name is required.")

    if method == WithdrawalRequest.Method.BANK:
        if not bank_name:
            errors.append("Bank name is required.")
        if not account_number:
            errors.append("Bank account number is required.")
    elif method in (WithdrawalRequest.Method.BKASH, WithdrawalRequest.Method.NAGAD):
        if not account_number:
            errors.append(f"{method.title()} number is required.")

    if errors:
        start_date, end_date, clamped = _parse_earnings_range(request)
        pending_qs, withdrawable_qs, pending_total, withdrawable_total = _earnings_data(
            request.user, start_date, end_date
        )
        return render(request, "contracts/earnings.html", {
            "start_date": start_date, "end_date": end_date, "today": timezone.localdate(),
            "date_range_clamped": clamped, "pending_contracts": pending_qs,
            "withdrawable_contracts": withdrawable_qs, "pending_total": pending_total,
            "withdrawable_total": withdrawable_total, "current_balance": current_balance,
            "my_withdrawals": WithdrawalRequest.objects.filter(freelancer=request.user)[:10],
            "withdrawal_errors": errors,
        })

    WithdrawalRequest.objects.create(
        freelancer=request.user,
        amount=amount,
        method=method,
        bank_name=bank_name,
        account_number=account_number,
        account_holder_name=account_holder_name,
    )

    return redirect("freelancer_earnings")


@user_passes_test(lambda u: u.is_authenticated and u.is_staff)
def staff_withdrawals(request):
    withdrawals = WithdrawalRequest.objects.select_related("freelancer").filter(
        status=WithdrawalRequest.Status.PENDING
    )
    return render(request, "contracts/staff_withdrawals.html", {"withdrawals": withdrawals})


@user_passes_test(lambda u: u.is_authenticated and u.is_staff)
@require_POST
def respond_to_withdrawal(request, pk):
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
        withdrawal.admin_note = request.POST.get("admin_note", "").strip()
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        Notification.objects.create(
            recipient=withdrawal.freelancer,
            message=f"Your withdrawal request of ৳{withdrawal.amount} was rejected.",
            link="/contracts/earnings/",
        )

    return redirect("staff_withdrawals")


@login_required
def download_earnings_pdf(request):
    start_date, end_date, _clamped = _parse_earnings_range(request)
    pending_qs, withdrawable_qs, pending_total, withdrawable_total = _earnings_data(
        request.user, start_date, end_date
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Gigframe — Earnings Statement", styles["Title"]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(f"Freelancer: {request.user.username}", styles["Normal"]))
    elements.append(Paragraph(
        f"Date range: {start_date.strftime('%d %b %Y')} &ndash; {end_date.strftime('%d %b %Y')}",
        styles["Normal"],
    ))
    elements.append(Paragraph(
        f"Generated: {timezone.localtime().strftime('%d %b %Y, %I:%M %p')}", styles["Normal"]
    ))
    elements.append(Spacer(1, 6 * mm))

    summary_rows = [
        ["Pending balance (in escrow)", f"\u09f3{pending_total:.2f}"],
        ["Withdrawable balance (paid out)", f"\u09f3{withdrawable_total:.2f}"],
        ["Total", f"\u09f3{(pending_total + withdrawable_total):.2f}"],
    ]
    summary_table = Table(summary_rows, colWidths=[100 * mm, 60 * mm])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 10 * mm))

    def _contract_table(title, qs, empty_msg):
        elements.append(Paragraph(title, styles["Heading3"]))
        if not qs:
            elements.append(Paragraph(empty_msg, styles["Normal"]))
            elements.append(Spacer(1, 6 * mm))
            return
        rows = [["Job", "Client", "Date", "Amount", "Your payout"]]
        for c in qs:
            row_date = c.completed_at or c.funded_at
            rows.append([
                Paragraph(c.job.title, styles["Normal"]),
                c.client.username,
                row_date.strftime("%d %b %Y") if row_date else "\u2014",
                f"\u09f3{c.amount:.2f}",
                f"\u09f3{c.freelancer_payout:.2f}",
            ])
        table = Table(rows, colWidths=[55 * mm, 30 * mm, 25 * mm, 25 * mm, 25 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d3b2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 10 * mm))

    _contract_table("Withdrawable \u2014 paid out in this range", withdrawable_qs, "No completed contracts in this range.")
    _contract_table("Pending \u2014 currently in escrow", pending_qs, "No pending contracts in this range.")

    doc.build(elements)
    buffer.seek(0)

    filename = f"gigframe-earnings-{request.user.username}-{start_date}-to-{end_date}.pdf"
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response