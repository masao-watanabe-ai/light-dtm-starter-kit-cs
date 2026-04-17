from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["demo"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/demo", response_class=HTMLResponse)
def demo(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "demo.html",
        {"request": request, "title": "Light DTM Starter"},
    )
