"""Explicit page routes; only built browser assets are publicly mounted."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Primitive foundation", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/browser", StaticFiles(directory=ROOT / "browser"), name="browser")
templates = Jinja2Templates(directory=ROOT / "app" / "templates")


@app.get("/")
def home():
    return RedirectResponse("/design/tokens/", status_code=303)


@app.get("/design/tokens/", response_class=HTMLResponse)
def design_tokens(request: Request):
    return templates.TemplateResponse(request=request, name="design/tokens/index.html")


@app.get("/design/components/", response_class=HTMLResponse)
def design_components(request: Request):
    return templates.TemplateResponse(request=request, name="design/components/index.html")
