import requests
from django.conf import settings

SANDBOX_BASE_URL = "https://sandbox.sslcommerz.com"


def initiate_payment(contract, request):
    """
    Step 1 of the payment flow: tell SSLCommerz "a customer wants to
    pay this amount for this contract," and get back a redirect URL
    to send the browser to (SSLCommerz's own hosted payment page).
    """
    success_url = request.build_absolute_uri(f"/contracts/{contract.pk}/payment/success/")
    fail_url = request.build_absolute_uri(f"/contracts/{contract.pk}/payment/fail/")
    cancel_url = request.build_absolute_uri(f"/contracts/{contract.pk}/payment/cancel/")

    payload = {
        "store_id": settings.SSLCOMMERZ_STORE_ID,
        "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
        "total_amount": str(contract.amount),
        "currency": "BDT",
        "tran_id": f"gigframe-contract-{contract.pk}",
        "success_url": success_url,
        "fail_url": fail_url,
        "cancel_url": cancel_url,
        "cus_name": contract.client.username,
        "cus_email": contract.client.email or "test@gigframe.local",
        "cus_add1": "Dhaka",
        "cus_city": "Dhaka",
        "cus_country": "Bangladesh",
        "cus_phone": "01700000000",
        "shipping_method": "NO",
        "product_name": contract.job.title,
        "product_category": "Service",
        "product_profile": "general",
    }

    response = requests.post(f"{SANDBOX_BASE_URL}/gwprocess/v4/api.php", data=payload)
    data = response.json()

    if data.get("status") == "SUCCESS":
        return data["GatewayPageURL"]
    return None


def validate_payment(val_id):
    """
    Step 2 of the payment flow: after SSLCommerz redirects the user
    back to our success_url, we do NOT trust that redirect alone.
    We call SSLCommerz's own Validation API to confirm the payment
    genuinely went through, and return the full response — we need
    `bank_tran_id` from here to be able to refund this payment later.
    """
    params = {
        "val_id": val_id,
        "store_id": settings.SSLCOMMERZ_STORE_ID,
        "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
        "format": "json",
    }
    response = requests.get(f"{SANDBOX_BASE_URL}/validator/api/validationserverAPI.php", params=params)
    data = response.json()

    if data.get("status") in ["VALID", "VALIDATED"]:
        return data
    return None


def initiate_refund(contract):
    """
    Reverses a funded contract's payment. This is a GET request with
    query parameters, same as validate_payment() — SSLCommerz's refund
    endpoint doesn't accept POST form data, which was causing it to
    return a non-JSON error page instead of a refund response.
    Needs bank_tran_id (not our own tran_id), saved at funding time.
    """
    params = {
        "bank_tran_id": contract.bank_tran_id,
        "store_id": settings.SSLCOMMERZ_STORE_ID,
        "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
        "refund_amount": str(contract.amount),
        "refund_remarks": contract.cancellation_reason or "Order cancelled",
        "refe_id": f"gigframe-refund-contract-{contract.pk}",
        "format": "json",
    }

    response = requests.get(
        f"{SANDBOX_BASE_URL}/validator/api/merchantTransIDvalidationAPI.php",
        params=params,
    )

    try:
        data = response.json()
    except ValueError:
        # SSLCommerz returned something that isn't JSON (HTML error
        # page, empty body, etc.) — treat as a failed refund rather
        # than crashing the whole request.
        return None

    if data.get("APIConnect") == "DONE":
        return data.get("refund_ref_id")
    return None