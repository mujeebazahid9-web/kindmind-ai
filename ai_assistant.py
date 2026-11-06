"""KindMind AI assistant: grounded chat plus a validated donation proposal.

The model has one tool, propose_donation. Whatever it returns is re-checked on
the server before it is shown to the visitor. Nothing in this file starts a
payment: the visitor must approve the proposal on the page first.
"""
import os
import time
from collections import defaultdict, deque

import payments
from projects_data import PROJECTS, get_project

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
MAX_HISTORY = 10
MAX_MESSAGE_CHARS = 1000
MIN_DONATION = 1
MAX_DONATION = 100


def payment_connected():
    """True only when Braintree sandbox keys are set. The assistant is told the truth."""
    return payments.configured()


IP_LIMIT, IP_WINDOW = 20, 600          # 20 requests per 10 minutes per visitor
GLOBAL_LIMIT, GLOBAL_WINDOW = 200, 3600  # 200 requests per hour for the whole site

PROPOSE_TOOL = {
    "name": "propose_donation",
    "description": (
        "Prepare a sample donation proposal for the visitor to review. Use it when the visitor "
        "wants to donate or asks you to recommend a project for an amount. It does not charge "
        "anyone: the visitor must approve it on the page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string", "enum": [p["slug"] for p in PROJECTS]},
            "amount_usd": {"type": "integer", "minimum": MIN_DONATION, "maximum": MAX_DONATION},
            "reason": {"type": "string", "description": "One or two sentences, based only on the project facts."},
        },
        "required": ["project_slug", "amount_usd", "reason"],
    },
}


class AssistantUnavailable(Exception):
    """Raised when no API key is configured."""


def project_facts():
    lines = []
    for p in PROJECTS:
        needs = "; ".join(f"{n['item']} (${n['cost']})" for n in p["needs"])
        lines.append(
            f"- slug: {p['slug']}\n"
            f"  title: {p['title']}\n"
            f"  category: {p['tag']}\n"
            f"  location: {p['location']}\n"
            f"  summary: {p['summary']}\n"
            f"  purpose: {p['purpose']}\n"
            f"  problem: {p['problem']}\n"
            f"  needs: {needs}\n"
            f"  funding goal: ${p['goal']}\n"
            f"  raised so far: ${p['amount_raised']}\n"
            f"  intended use of funds: {p['usage']}"
        )
    return "\n".join(lines)


def build_system_prompt():
    if payment_connected():
        payment_line = (
            "Donating works like this: you prepare a proposal, the visitor approves it, and then a "
            "Braintree (a PayPal service) sandbox TEST payment runs. No real money moves."
        )
    else:
        payment_line = (
            "The payment step is NOT connected yet in this version. You can prepare a proposal, but "
            "no payment can be made. Say so if asked."
        )
    return (
        "You are the KindMind AI assistant on a hackathon demo website that helps people explore "
        "educational causes.\n\n"
        "Rules:\n"
        "- Answer only from the PROJECT FACTS and PLATFORM FACTS below.\n"
        "- If the information is not there, say: I don't have that information.\n"
        "- Never invent beneficiaries, statistics, success stories, project updates, donation "
        "records, or impact claims.\n"
        "- All projects are SAMPLE demo projects, not real or verified initiatives. Say so when relevant.\n"
        "- You do not verify organizations, and you can make mistakes.\n"
        "- You cannot charge anyone and you never say a payment was made.\n"
        "- When the visitor wants to donate, or asks for a recommendation with an amount, call "
        "propose_donation. Whole US dollars only, from $1 to $100.\n"
        "- Keep answers short, friendly and in simple English.\n\n"
        "PLATFORM FACTS:\n"
        "- KindMind AI is a hackathon demonstration built for the PayPal AI Hackathon 2026.\n"
        "- It is inspired by the vision of Mujeeba Foundation for Learning and Development, which is "
        "still in development and is not a registered organization.\n"
        f"- {payment_line}\n\n"
        "PROJECT FACTS:\n"
        f"{project_facts()}\n"
    )


def sanitize_history(raw):
    """Keep only valid user/assistant text messages, trimmed, ending with a user message."""
    cleaned = []
    if not isinstance(raw, list):
        return cleaned
    for item in raw:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()[:MAX_MESSAGE_CHARS]
        if content:
            cleaned.append({"role": role, "content": content})
    cleaned = cleaned[-MAX_HISTORY:]
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    return cleaned


def validate_proposal(tool_input):
    """Re-check what the model asked for. Returns a safe dict, or None."""
    if not isinstance(tool_input, dict):
        return None
    slug = tool_input.get("project_slug")
    project = get_project(slug) if isinstance(slug, str) else None
    if project is None:
        return None
    amount = tool_input.get("amount_usd")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or int(amount) != amount:
        return None
    amount = int(amount)
    remaining = project["goal"] - project["amount_raised"]
    if remaining <= 0 or not MIN_DONATION <= amount <= min(MAX_DONATION, remaining):
        return None
    return {
        "project_slug": project["slug"],
        "project_title": project["title"],
        "amount_usd": amount,
        "reason": str(tool_input.get("reason", ""))[:300],
    }


_ip_hits = defaultdict(deque)
_global_hits = deque()


def _prune(queue, window, now):
    while queue and now - queue[0] > window:
        queue.popleft()


def allow(ip):
    """Simple in-memory limits that protect the API credit."""
    now = time.time()
    ip_queue = _ip_hits[ip]
    _prune(ip_queue, IP_WINDOW, now)
    _prune(_global_hits, GLOBAL_WINDOW, now)
    if len(ip_queue) >= IP_LIMIT or len(_global_hits) >= GLOBAL_LIMIT:
        return False
    ip_queue.append(now)
    _global_hits.append(now)
    return True


_client = None


def get_client():
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        from anthropic import Anthropic
        _client = Anthropic(api_key=key)
    return _client


def respond(raw_history, client=None):
    messages = sanitize_history(raw_history)
    if not messages or messages[-1]["role"] != "user":
        raise ValueError("A user message is required.")
    client = client or get_client()
    if client is None:
        raise AssistantUnavailable()

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=build_system_prompt(),
        messages=messages,
        tools=[PROPOSE_TOOL],
    )

    texts, proposal = [], None
    for block in response.content:
        if block.type == "text" and block.text.strip():
            texts.append(block.text.strip())
        elif block.type == "tool_use" and block.name == "propose_donation" and proposal is None:
            proposal = validate_proposal(block.input)

    reply = "\n\n".join(texts)
    if not reply:
        reply = (
            "I've prepared a sample donation proposal for you to review below."
            if proposal
            else "Sorry, I couldn't prepare an answer. Please try asking again."
        )
    if proposal and payment_connected():
        # Signed so the payment step can only charge exactly what the server validated.
        proposal["token"] = payments.make_proposal_token(
            proposal["project_slug"], proposal["amount_usd"]
        )
    return {"reply": reply, "proposal": proposal, "payment_enabled": payment_connected()}
