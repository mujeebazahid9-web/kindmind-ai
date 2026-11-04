"""KindMind AI - main web application.

Stage 2: pages with clearly labelled demo data, plus the AI assistant.
Not connected yet: the sandbox payment step.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

import ai_assistant
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


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
