from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    """Web利用規約ページ"""
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "discord_id": request.session.get("discord_id")
    })

@router.get("/bot-terms", response_class=HTMLResponse)
async def bot_terms_page(request: Request):
    """BOT利用規約ページ"""
    return templates.TemplateResponse("bot_terms.html", {
        "request": request,
        "discord_id": request.session.get("discord_id")
    })

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """プライバシーポリシーページ"""
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "discord_id": request.session.get("discord_id")
    })