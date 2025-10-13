from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from utils.auth import get_current_user
import supabase_client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/status")
async def get_user_status(discord_id: str = Depends(get_current_user)):
    """ユーザーステータスAPI"""
    player = supabase_client.get_player(discord_id)
    
    if not player:
        return JSONResponse(
            content={
                "status": "error",
                "message": "プレイヤーデータが見つかりません",
                "discord_id": discord_id
            },
            media_type="application/json; charset=utf-8",
            status_code=404
        )
    
    return JSONResponse(
        content={
            "status": "success",
            "message": "ログイン済みです",
            "discord_id": discord_id,
            "player": player
        },
        media_type="application/json; charset=utf-8"
    )

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, discord_id: str = Depends(get_current_user)):
    """ユーザーがログイン後に到達するダッシュボードページ"""
    player = supabase_client.get_player(discord_id)
    
    if not player:
        supabase_client.create_player(discord_id)
        player = supabase_client.get_player(discord_id)
    
    equipped = supabase_client.get_equipped_items(discord_id)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "equipped_weapon": equipped.get("weapon", "なし"),
        "equipped_armor": equipped.get("armor", "なし")
    })
 fastapi import APIRouter, Depends