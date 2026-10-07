"""Explicit page routes; only built browser assets are publicly mounted."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Minimal Webapp")
app.mount("/browser", StaticFiles(directory=ROOT / "browser"), name="browser")
templates = Jinja2Templates(directory=ROOT / "app" / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request=request, name="about.html")
