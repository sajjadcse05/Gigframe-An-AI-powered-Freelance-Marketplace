from django.conf import settings
from django.db import models


class Contract(models.Model):
    """
    Created automatically the moment a Client accepts a Freelancer's
    Proposal. Tracks the escrow-style lifecycle: pay in -> freelancer
    delivers -> client approves -> payment considered released.
    Can also be cancelled (with refund) if the freelancer is unable
    to complete the work after funding.
    """

    PLATFORM_COMMISSION_PERCENT = 15

    # A cancellation request auto-resolves after this many hours if
    # the other party never responds — mirrors Fiverr's Resolution
    # Center behavior, so nobody's money gets stuck indefinitely.
    CANCELLATION_AUTO_ACCEPT_HOURS = 48

    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Awaiting Payment"
        FUNDED = "FUNDED", "Funded (in escrow)"
        DELIVERED = "DELIVERED", "Delivered — awaiting approval"
        COMPLETED = "COMPLETED", "Completed & Paid Out"
        CANCELLED = "CANCELLED", "Cancelled & Refunded"

    job = models.OneToOneField("jobs.Job", on_delete=models.CASCADE, related_name="contract")
    proposal = models.OneToOneField("jobs.Proposal", on_delete=models.CASCADE, related_name="contract")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contracts_as_client")
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contracts_as_freelancer")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)

    # SSLCommerz-specific fields — needed to track and later verify the transaction.
    transaction_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    sslcommerz_val_id = models.CharField(max_length=100, blank=True)
    bank_tran_id = models.CharField(
        max_length=100, blank=True,
        help_text="SSLCommerz's own bank transaction ID — required to initiate a refund later",
    )

    # Cancellation / refund fields
    cancellation_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cancellations_requested",
    )
    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancellation_requested_at = models.DateTimeField(null=True, blank=True)
    refund_ref_id = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    funded_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Contract for '{self.job.title}' ({self.status})"

    @property
    def platform_fee(self):
        return round(self.amount * self.PLATFORM_COMMISSION_PERCENT / 100, 2)

    @property
    def freelancer_payout(self):
        return self.amount - self.platform_fee

    @property
    def other_party(self, user=None):
        """Given one side of the contract, returns the other."""
        pass  # not used — kept views explicit instead, see views.py

    @property
    def cancellation_pending(self):
        return self.cancellation_requested_by is not None and self.status in (
            self.Status.FUNDED, self.Status.DELIVERED
        )

    @property
    def cancellation_deadline_passed(self):
        if not self.cancellation_requested_at:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() >= self.cancellation_requested_at + timedelta(hours=self.CANCELLATION_AUTO_ACCEPT_HOURS)


class Review(models.Model):
    """
    A rating + written review, left by one party of a completed
    Contract about the other. Both the Client and the Freelancer can
    leave one review each — `unique_together` stops either from
    submitting more than one review per contract.
    """

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_given")
    reviewee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["contract", "reviewer"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reviewer.username} -> {self.reviewee.username}: {self.rating}★"


class WithdrawalRequest(models.Model):
    """
    A freelancer's request to cash out their withdrawable balance.
    No real payout gateway is wired up — an admin manually marks
    these APPROVED/REJECTED after actually sending the money.
    """

    class Method(models.TextChoices):
        BANK = "BANK", "Bank Transfer"
        BKASH = "BKASH", "bKash"
        NAGAD = "NAGAD", "Nagad"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved & Paid"
        REJECTED = "REJECTED", "Rejected"

    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawal_requests"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices)

    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(
        max_length=50, blank=True,
        help_text="Bank account number, or bKash/Nagad phone number",
    )
    account_holder_name = models.CharField(max_length=150, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_note = models.CharField(max_length=255, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.freelancer.username} — ৳{self.amount} ({self.status})"