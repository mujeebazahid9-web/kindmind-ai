"""KindMind AI - main web application.

Stage 3: pages with clearly labelled demo data, the AI assistant, and the
Braintree SANDBOX payment step (test payments only, no real money).
"""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

import ai_assistant
import payments
from projects_data import PROJECTS, get_project

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger("kindmind")

app = FastAPI(title="KindMind AI")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"projects": PROJECTS}
    )


@app.get("/causes", response_class=HTMLResponse)
def causes(request: Request):
    return templates.TemplateResponse(
        request, "causes.html", {"projects": PROJECTS}
    )


@app.get("/causes/{slug}", response_class=HTMLResponse)
def cause_detail(request: Request, slug: str):
    project = get_project(slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse(
        request, "project.html", {"project": project}
    )


@app.get("/assistant", response_class=HTMLResponse)
def assistant_page(request: Request):
    return templates.TemplateResponse(request, "assistant.html", {})


@app.post("/api/chat")
async def chat(request: Request):
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")

    if not ai_assistant.allow(ip):
        return JSONResponse(
            {"error": "Too many questions in a short time. Please wait a few minutes and try again."},
            status_code=429,
        )

    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 20000:
        return JSONResponse({"error": "That message is too long."}, status_code=413)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request."}, status_code=400)
    messages = data.get("messages") if isinstance(data, dict) else None
    if not isinstance(messages, list):
        return JSONResponse({"error": "Invalid request."}, status_code=400)

    try:
        result = await run_in_threadpool(ai_assistant.respond, messages)
    except ai_assistant.AssistantUnavailable:
        return JSONResponse(
            {"error": "The AI assistant is not configured on this server yet."}, status_code=503
        )
    except ValueError:
        return JSONResponse({"error": "Please type a question first."}, status_code=400)
    except Exception as exc:  # never show internal details to visitors
        logger.error("AI request failed: %s", type(exc).__name__)
        return JSONResponse(
            {"error": "The AI service had a problem. Please try again in a moment."}, status_code=502
        )
    return JSONResponse(result)


def _client_ip(request: Request):
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@app.get("/api/payment/client-token")
async def payment_client_token(request: Request):
    if not payments.configured():
        return JSONResponse({"error": "The sandbox payment step is not configured on this server."}, status_code=503)
    if not payments.allow_payment(_client_ip(request)):
        return JSONResponse({"error": "Too many attempts. Please wait a while and try again."}, status_code=429)
    try:
        token = await run_in_threadpool(payments.client_token)
    except Exception as exc:
        logger.error("Braintree client token failed: %s", type(exc).__name__)
        return JSONResponse({"error": "The payment service had a problem. Please try again."}, status_code=502)
    return JSONResponse({"client_token": token})


@app.post("/api/payment/checkout")
async def payment_checkout(request: Request):
    if not payments.configured():
        return JSONResponse({"error": "The sandbox payment step is not configured on this server."}, status_code=503)
    if not payments.allow_payment(_client_ip(request)):
        return JSONResponse({"error": "Too many attempts. Please wait a while and try again."}, status_code=429)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 5000:
        return JSONResponse({"error": "Invalid request."}, status_code=413)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request."}, status_code=400)
    if not isinstance(data, dict):
        return JSONResponse({"error": "Invalid request."}, status_code=400)
    try:
        record = await run_in_threadpool(
            payments.checkout, data.get("proposal_token"), data.get("payment_nonce")
        )
    except payments.PaymentRejected as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:  # never show internal details to visitors
        logger.error("Braintree checkout failed: %s", type(exc).__name__)
        return JSONResponse({"error": "The payment service had a problem. Nothing was charged. Please try again."}, status_code=502)
    return JSONResponse({"transaction_id": record["transaction_id"], "url": f"/payment/confirmation/{record['transaction_id']}"})


@app.get("/payment/confirmation/{transaction_id}", response_class=HTMLResponse)
def payment_confirmation(request: Request, transaction_id: str):
    # Only payments that really exist in the server log can be shown.
    record = payments.find_payment(transaction_id) if len(transaction_id) < 64 else None
    if record is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return templates.TemplateResponse(request, "confirmation.html", {"payment": record})


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
