"""Checks for the sandbox payment logic. Run:  python tests/test_payments.py
Braintree is replaced by a fake gateway, so no network and no keys are needed."""
import os, sys, tempfile, time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["KINDMIND_PAYMENT_LOG"] = str(Path(tempfile.mkdtemp()) / "pay.jsonl")
for k in ("BRAINTREE_MERCHANT_ID", "BRAINTREE_PUBLIC_KEY", "BRAINTREE_PRIVATE_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(k, None)

import payments, ai_assistant

ok = lambda name, cond: print(("PASS " if cond else "FAIL ") + name) or (cond or sys.exit(1))

class Tx:
    def __init__(self, amount, status="submitted_for_settlement", id="tx_test_1"):
        self.amount, self.status, self.id = Decimal(amount), status, id
class Result:
    def __init__(self, ok, tx=None): self.is_success, self.transaction = ok, tx
class FakeGateway:
    def __init__(self, result=None): self.calls, self.result = [], result
    @property
    def transaction(self):
        outer = self
        class T:
            def sale(self, params):
                outer.calls.append(params)
                return outer.result or Result(True, Tx(params["amount"], id=f"tx_{len(outer.calls)}"))
        return T()

# not configured -> assistant says so, no tokens issued
ok("not configured", not payments.configured() and not ai_assistant.payment_connected())
ok("prompt says not connected", "NOT connected" in ai_assistant.build_system_prompt())
os.environ.update(BRAINTREE_MERCHANT_ID="m", BRAINTREE_PUBLIC_KEY="p", BRAINTREE_PRIVATE_KEY="k-test-only")
ok("configured", payments.configured() and ai_assistant.payment_connected())
ok("prompt says sandbox test", "TEST payment" in ai_assistant.build_system_prompt())

# tokens
t = payments.make_proposal_token("digital-literacy-lab", 20)
r = payments.read_proposal_token(t)
ok("token round trip", r["amount_usd"] == 20 and r["project"]["slug"] == "digital-literacy-lab")
def rejects(name, token, now=None):
    try: payments.read_proposal_token(token, now=now); ok(name, False)
    except payments.PaymentRejected: ok(name, True)
body, sig = t.split(".")
rejects("tampered signature", body + "." + sig[:-2] + ("AA" if sig[-2:] != "AA" else "BB"))
import base64, json
forged = base64.urlsafe_b64encode(json.dumps({"s":"digital-literacy-lab","a":100,"e":int(time.time())+999,"n":"zz"}).encode()).decode().rstrip("=")
rejects("forged amount", forged + "." + sig)
rejects("expired", t, now=time.time() + 3600)
rejects("garbage", "not-a-token"); rejects("none", None); rejects("empty", "")
for name, args in [("unknown slug", ("nope", 5)), ("zero", ("digital-literacy-lab", 0)), ("over cap", ("digital-literacy-lab", 101)),
                   ("float", ("digital-literacy-lab", 2.5)), ("string", ("digital-literacy-lab", "5")), ("bool", ("digital-literacy-lab", True))]:
    try: payments.make_proposal_token(*args); ok("refuse to sign " + name, False)
    except payments.PaymentRejected: ok("refuse to sign " + name, True)

# assistant attaches a token only to validated proposals
class B:
    def __init__(self, **kw): self.__dict__.update(kw)
class FC:
    def __init__(self, blocks): self.blocks = blocks
    @property
    def messages(self):
        outer = self
        class M:
            def create(self, **kw): return B(content=outer.blocks)
        return M()
good = {"project_slug": "science-kits-for-classrooms", "amount_usd": 15, "reason": "Hands-on."}
res = ai_assistant.respond([{"role": "user", "content": "x"}], client=FC([B(type="tool_use", name="propose_donation", input=good)]))
ok("proposal carries a valid token", payments.read_proposal_token(res["proposal"]["token"])["amount_usd"] == 15 and res["payment_enabled"])
res = ai_assistant.respond([{"role": "user", "content": "x"}], client=FC([B(type="tool_use", name="propose_donation", input={**good, "amount_usd": 5000})]))
ok("bad proposal gets no token", res["proposal"] is None)

# checkout
gw = FakeGateway()
tok = payments.make_proposal_token("village-library-corner", 20)
rec = payments.checkout(tok, "fake-valid-nonce", gateway=gw)
ok("checkout charges token amount in sandbox", gw.calls[0]["amount"] == "20.00" and gw.calls[0]["options"]["submit_for_settlement"] and rec["sandbox"])
ok("payment is logged and findable", payments.find_payment(rec["transaction_id"])["amount_usd"] == 20)
ok("unknown transaction not found", payments.find_payment("tx_unknown") is None)
try: payments.checkout(tok, "fake-valid-nonce", gateway=gw); ok("proposal cannot be paid twice", False)
except payments.PaymentRejected: ok("proposal cannot be paid twice", True)
ok("only one charge was made", len(gw.calls) == 1)
for name, bad in [("declined", FakeGateway(Result(False))), ("amount mismatch", FakeGateway(Result(True, Tx("99.00")))),
                  ("bad status", FakeGateway(Result(True, Tx("5.00", status="gateway_rejected"))))]:
    try: payments.checkout(payments.make_proposal_token("village-library-corner", 5), "n", gateway=bad); ok(name + " not recorded", False)
    except payments.PaymentRejected: ok(name + " not recorded", True)
ok("failed payments left no record", len(payments._read_log()) == 1)
for name, nonce in [("missing nonce", ""), ("non-string nonce", 5)]:
    try: payments.checkout(payments.make_proposal_token("village-library-corner", 5), nonce, gateway=gw); ok(name, False)
    except payments.PaymentRejected: ok(name, True)

# rate limit
payments._pay_hits.clear()
ok("pay limit", [payments.allow_payment("9.9.9.9") for _ in range(12)].count(False) == 2)
print("ALL PAYMENT CHECKS PASSED")
