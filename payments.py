"""KindMind AI sandbox payments (Braintree, a PayPal service).

SANDBOX ONLY. Every payment made through this module is a test payment: no real
money moves. The server decides what can be paid:

1. The AI assistant proposes a donation. The server validates it and signs it
   into a short-lived proposal token (slug + whole-dollar amount + expiry).
2. The visitor approves it on the page and enters sandbox test card details in
   Braintree's hosted fields (card data never reaches this server).
3. The checkout route accepts ONLY a valid, unexpired, unused proposal token.
   The amount and project come from the token, never from the browser.
4. After Braintree answers, the result is checked and written to a small log.
   The confirmation page shows only payments that exist in that log.
"""
import base64
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path

from projects_data import get_project

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = Path(os.environ.get("KINDMIND_PAYMENT_LOG", BASE_DIR / "data" / "sandbox_payments.jsonl"))

MIN_DONATION = 1
MAX_DONATION = 100
TOKEN_TTL_SECONDS = 30 * 60           # a proposal can be paid within 30 minutes
PAY_LIMIT, PAY_WINDOW = 10, 3600      # 10 payment attempts per hour per visitor

_lock = threading.Lock()
_gateway = None
_pay_hits = {}


class PaymentUnavailable(Exception):
    """Raised when Braintree sandbox keys are not configured."""


class PaymentRejected(Exception):
    """Raised when a payment request is invalid. The message is safe to show."""


# ---------------------------------------------------------------- configuration

def configured():
    return all(
        os.environ.get(name)
        for name in ("BRAINTREE_MERCHANT_ID", "BRAINTREE_PUBLIC_KEY", "BRAINTREE_PRIVATE_KEY")
    )


def get_gateway():
    """Create the Braintree gateway once. Always the SANDBOX environment."""
    global _gateway
    if _gateway is None:
        if not configured():
            raise PaymentUnavailable()
        import braintree

        _gateway = braintree.BraintreeGateway(
            braintree.Configuration(
                braintree.Environment.Sandbox,
                merchant_id=os.environ["BRAINTREE_MERCHANT_ID"],
                public_key=os.environ["BRAINTREE_PUBLIC_KEY"],
                private_key=os.environ["BRAINTREE_PRIVATE_KEY"],
            )
        )
    return _gateway


def client_token():
    """Token the browser needs to show Braintree's hosted card fields."""
    return get_gateway().client_token.generate()


# ------------------------------------------------------------- proposal tokens

def _secret():
    explicit = os.environ.get("KINDMIND_SECRET")
    if explicit:
        return explicit.encode()
    # No extra setup needed: derive a signing secret from the sandbox private key.
    base = os.environ.get("BRAINTREE_PRIVATE_KEY", "")
    return hashlib.sha256(("kindmind-proposal:" + base).encode()).digest()


def _b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def check_amount(project, amount):
    """Shared rule: whole dollars, within limits, never more than the remaining goal."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        return False
    remaining = project["goal"] - project["amount_raised"]
    return remaining > 0 and MIN_DONATION <= amount <= min(MAX_DONATION, remaining)


def make_proposal_token(project_slug, amount_usd, now=None):
    project = get_project(project_slug)
    if project is None or not check_amount(project, amount_usd):
        raise PaymentRejected("This proposal is not valid.")
    payload = {
        "s": project_slug,
        "a": amount_usd,
        "e": int((now or time.time()) + TOKEN_TTL_SECONDS),
        "n": _b64(os.urandom(9)),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_proposal_token(token, now=None):
    """Return the signed proposal, or raise PaymentRejected."""
    bad = PaymentRejected("This proposal is no longer valid. Please ask the assistant for a new one.")
    if not isinstance(token, str) or token.count(".") != 1 or len(token) > 600:
        raise bad
    body, sig = token.split(".")
    expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise bad
    try:
        payload = json.loads(_unb64(body))
        slug, amount, expires, nonce = payload["s"], payload["a"], payload["e"], payload["n"]
    except Exception:
        raise bad
    project = get_project(slug) if isinstance(slug, str) else None
    if project is None or not check_amount(project, amount) or not isinstance(nonce, str):
        raise bad
    if (now or time.time()) > expires:
        raise bad
    return {"project": project, "amount_usd": amount, "order_id": nonce}


# ------------------------------------------------------------------ payment log

def _read_log():
    if not LOG_PATH.exists():
        return []
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def _append_log(record):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def find_payment(transaction_id):
    for record in _read_log():
        if record.get("transaction_id") == transaction_id:
            return record
    return None


def already_used(order_id):
    return any(r.get("order_id") == order_id for r in _read_log())


# --------------------------------------------------------------------- limiting

def allow_payment(ip, now=None):
    now = now or time.time()
    hits = _pay_hits.setdefault(ip, [])
    hits[:] = [t for t in hits if now - t < PAY_WINDOW]
    if len(hits) >= PAY_LIMIT:
        return False
    hits.append(now)
    return True


# --------------------------------------------------------------------- checkout

def checkout(proposal_token, payment_nonce, gateway=None, now=None):
    """Charge the sandbox test payment for a signed proposal.

    Returns a dict describing the verified result. Raises PaymentRejected when
    the request is invalid or Braintree declines it.
    """
    if not isinstance(payment_nonce, str) or not payment_nonce or len(payment_nonce) > 200:
        raise PaymentRejected("Payment details are missing. Please try again.")
    proposal = read_proposal_token(proposal_token, now=now)
    gateway = gateway or get_gateway()

    with _lock:  # one checkout at a time per process, so a proposal is paid once
        if already_used(proposal["order_id"]):
            raise PaymentRejected("This proposal was already paid. Ask the assistant for a new one.")
        result = gateway.transaction.sale(
            {
                "amount": f"{proposal['amount_usd']}.00",
                "payment_method_nonce": payment_nonce,
                "order_id": proposal["order_id"],
                "options": {"submit_for_settlement": True},
            }
        )
        if not result.is_success or result.transaction is None:
            raise PaymentRejected(
                "The sandbox payment was not accepted. Please check the test card details and try again."
            )
        tx = result.transaction
        # Verify what Braintree actually recorded, not what we asked for.
        if str(tx.amount) != f"{proposal['amount_usd']}.00" or str(tx.status) not in (
            "authorized",
            "submitted_for_settlement",
            "settling",
            "settled",
            "settlement_pending",
        ):
            raise PaymentRejected("The sandbox payment could not be verified. Nothing was recorded.")
        record = {
            "transaction_id": tx.id,
            "order_id": proposal["order_id"],
            "project_slug": proposal["project"]["slug"],
            "project_title": proposal["project"]["title"],
            "amount_usd": proposal["amount_usd"],
            "status": str(tx.status),
            "sandbox": True,
            "time": int(time.time()),
        }
        _append_log(record)
    return record
