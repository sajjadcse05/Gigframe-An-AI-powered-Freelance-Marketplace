from django.urls import path

from .views import (
    contract_detail, start_payment, payment_success, payment_fail,
    payment_cancel, mark_delivered, approve_and_release, leave_review,
    request_cancellation, respond_to_cancellation,
    freelancer_earnings, download_earnings_pdf,
    client_contracts, request_withdrawal, staff_withdrawals, respond_to_withdrawal,
)

urlpatterns = [
    path("<int:pk>/", contract_detail, name="contract_detail"),
    path("<int:pk>/pay/", start_payment, name="start_payment"),
    path("<int:pk>/payment/success/", payment_success, name="payment_success"),
    path("<int:pk>/payment/fail/", payment_fail, name="payment_fail"),
    path("<int:pk>/payment/cancel/", payment_cancel, name="payment_cancel"),
    path("<int:pk>/deliver/", mark_delivered, name="mark_delivered"),
    path("<int:pk>/approve/", approve_and_release, name="approve_and_release"),
    path("<int:pk>/review/", leave_review, name="leave_review"),
    path("<int:pk>/request-cancellation/", request_cancellation, name="request_cancellation"),
    path("<int:pk>/respond-cancellation/", respond_to_cancellation, name="respond_to_cancellation"),

    path("earnings/", freelancer_earnings, name="freelancer_earnings"),
    path("earnings/pdf/", download_earnings_pdf, name="download_earnings_pdf"),
    path("earnings/withdraw/", request_withdrawal, name="request_withdrawal"),

    path("my-contracts/", client_contracts, name="client_contracts"),

    path("staff/withdrawals/", staff_withdrawals, name="staff_withdrawals"),
    path("staff/withdrawals/<int:pk>/respond/", respond_to_withdrawal, name="respond_to_withdrawal"),
]