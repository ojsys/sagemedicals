"""
Paystack payment service.

All API calls use stdlib urllib — no extra dependencies.
Amounts are always in kobo (naira × 100).

Public API:
  initialize(invoice, initiated_by, callback_url) → PaystackTransaction
  verify(reference)                               → PaystackTransaction
  handle_webhook(raw_body, signature_header)       → PaystackTransaction | None
"""
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.utils import timezone


PAYSTACK_BASE = "https://api.paystack.co"


def _secret():
    return getattr(settings, "PAYSTACK_SECRET_KEY", "")


def _is_live():
    """True only when a real Paystack key (sk_test_* or sk_live_*) is configured."""
    key = _secret()
    return key.startswith("sk_test_") or key.startswith("sk_live_")


def _headers():
    return {
        "Authorization": f"Bearer {_secret()}",
        "Content-Type": "application/json",
    }


def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{PAYSTACK_BASE}{path}",
        data=data,
        headers=_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _get(path):
    req = urllib.request.Request(
        f"{PAYSTACK_BASE}{path}",
        headers=_headers(),
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _make_reference():
    return f"SAGE-{secrets.token_hex(10).upper()}"


def initialize(invoice, initiated_by, callback_url):
    """
    Create a PaystackTransaction and call Paystack /transaction/initialize.
    Returns the PaystackTransaction instance (with authorization_url set).
    Raises ValueError if the API call fails or balance is zero.
    """
    from billing.models import PaystackTransaction

    balance = invoice.balance
    if balance <= 0:
        raise ValueError("Invoice has no outstanding balance.")

    amount_kobo = int(balance * 100)
    reference = _make_reference()

    patient = invoice.patient
    email = getattr(patient, "email", "") or f"patient{patient.pk}@sagemedical.ng"

    tx = PaystackTransaction.objects.create(
        invoice=invoice,
        reference=reference,
        amount_kobo=amount_kobo,
        customer_email=email,
        initiated_by=initiated_by,
        status=PaystackTransaction.Status.PENDING,
    )

    if not _is_live():
        # Dev mode: skip real API call, return a dummy URL
        tx.authorization_url = f"https://paystack.com/pay/dev-{reference}"
        tx.save(update_fields=["authorization_url"])
        return tx

    try:
        resp = _post("/transaction/initialize", {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "invoice_number": invoice.invoice_number,
                "patient": patient.full_name,
                "hospital_number": patient.hospital_number,
                "cancel_action": callback_url,
            },
        })
    except urllib.error.URLError as exc:
        tx.status = PaystackTransaction.Status.FAILED
        tx.gateway_response = str(exc)
        tx.save(update_fields=["status", "gateway_response"])
        raise ValueError(f"Paystack API error: {exc}") from exc

    if not resp.get("status"):
        tx.status = PaystackTransaction.Status.FAILED
        tx.gateway_response = resp.get("message", "Unknown error")
        tx.save(update_fields=["status", "gateway_response"])
        raise ValueError(f"Paystack: {resp.get('message', 'initialization failed')}")

    data = resp["data"]
    tx.authorization_url = data["authorization_url"]
    tx.save(update_fields=["authorization_url"])
    return tx


def verify(reference):
    """
    Verify a transaction with Paystack and update its status.
    If successful and not yet recorded, creates a Payment on the invoice.
    Returns the updated PaystackTransaction.
    """
    from billing.models import Payment, PaystackTransaction
    from billing.services import record_payment

    try:
        tx = PaystackTransaction.objects.select_related("invoice", "initiated_by").get(
            reference=reference
        )
    except PaystackTransaction.DoesNotExist:
        raise ValueError(f"Transaction {reference} not found.")

    if tx.status == PaystackTransaction.Status.SUCCESS:
        return tx  # Already verified, idempotent

    if not _is_live():
        # Dev mode: simulate success
        tx.status = PaystackTransaction.Status.SUCCESS
        tx.verified_at = timezone.now()
        tx.gateway_response = "dev-mode simulated"
        tx.save(update_fields=["status", "verified_at", "gateway_response"])
        _record_success(tx)
        return tx

    try:
        resp = _get(f"/transaction/verify/{reference}")
    except urllib.error.URLError as exc:
        raise ValueError(f"Paystack verify API error: {exc}") from exc

    if not resp.get("status"):
        raise ValueError(f"Paystack verification failed: {resp.get('message')}")

    data = resp["data"]
    tx.paystack_id = str(data.get("id", ""))
    tx.gateway_response = data.get("gateway_response", "")
    tx.verified_at = timezone.now()

    if data.get("status") == "success":
        paid_kobo = data.get("amount", 0)
        if paid_kobo != tx.amount_kobo:
            # Amount mismatch — log but still record
            tx.gateway_response += f" [AMOUNT MISMATCH: expected {tx.amount_kobo} got {paid_kobo}]"
        tx.status = PaystackTransaction.Status.SUCCESS
        tx.save(update_fields=["paystack_id", "gateway_response", "verified_at", "status"])
        _record_success(tx)
    else:
        tx.status = PaystackTransaction.Status.FAILED
        tx.save(update_fields=["paystack_id", "gateway_response", "verified_at", "status"])

    return tx


def _record_success(tx):
    """Create a Payment record for a verified transaction (idempotent)."""
    from billing.models import Payment
    from billing.services import record_payment

    already_paid = Payment.objects.filter(reference=tx.reference).exists()
    if already_paid:
        return

    record_payment(
        invoice=tx.invoice,
        amount=Decimal(tx.amount_kobo) / 100,
        mode="online",
        reference=tx.reference,
        cashier=tx.initiated_by or _get_system_user(),
        notes=f"Paystack {tx.paystack_id or 'dev-mode'}",
    )


def _get_system_user():
    from accounts.models import User
    return User.objects.filter(is_superuser=True).first()


def handle_webhook(raw_body: bytes, signature_header: str):
    """
    Process a Paystack webhook.
    Verifies HMAC-SHA512 signature before touching the database.
    Returns the PaystackTransaction if relevant, else None.
    Raises ValueError on bad signature.
    """
    if not _is_live():
        return None

    expected = hmac.new(
        _secret().encode(), raw_body, hashlib.sha512
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise ValueError("Invalid Paystack webhook signature.")

    event = json.loads(raw_body)
    if event.get("event") != "charge.success":
        return None  # We only care about successful charges

    reference = event.get("data", {}).get("reference", "")
    if not reference:
        return None

    try:
        return verify(reference)
    except ValueError:
        return None
