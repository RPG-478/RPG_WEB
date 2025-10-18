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

from fastapi import Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os

templates = Jinja2Templates(directory="templates")
SECRET_KEY = os.getenv("SESSION_SECRET")
ALGORITHM = "HS256"

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session_token: str = Cookie(None)):
    """ダッシュボード (アクセス制限付き)"""
    from utils.security import get_client_ip
    import supabase_client

    # ログインチェック
    if not session_token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
        discord_id = payload.get("discord_id")
    except JWTError:
        return RedirectResponse(url="/auth/login", status_code=302)

    client_ip = get_client_ip(request)

    # 10分以内のダッシュボードアクセス回数チェック
    ten_min_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()

    dashboard_access = supabase_client.supabase.table("dashboard_access").select("*").eq(
        "ip_address", client_ip
    ).gte("accessed_at", ten_min_ago).execute()

    # 10分間に100回以上 = 異常
    if dashboard_access.data and len(dashboard_access.data) >= 100:
        return templates.TemplateResponse(
            "rate_limit.html",
            {"request": request},
            status_code=429
        )

    # アクセス記録
    supabase_client.supabase.table("dashboard_access").insert({
        "ip_address": client_ip,
        "accessed_at": datetime.utcnow().isoformat()
    }).execute()

    # プレイヤーデータ取得
    player_data = supabase_client.supabase.table("players").select("*").eq("user_id", discord_id).execute()

    if not player_data.data:
        player = {}
        equipped_weapon = "なし"
        equipped_armor = "なし"
    else:
        player = player_data.data[0]
        equipped_weapon = player.get("equipped_weapon", "なし")
        equipped_armor = player.get("equipped_armor", "なし")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "equipped_weapon": equipped_weapon,
        "equipped_armor": equipped_armor
    })