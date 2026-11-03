"""KindMind AI - main web application (Stage 1: pages with clearly labelled demo data).

Not yet connected: the AI assistant and PayPal Sandbox checkout.
Those are added in later stages.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from projects_data import PROJECTS, get_project

BASE_DIR = Path(__file__).resolve().parent

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
def assistant(request: Request):
    return templates.TemplateResponse(request, "assistant.html", {})


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
