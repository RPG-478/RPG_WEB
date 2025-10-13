from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import supabase_client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 環境変数から取得 (GitHubに公開されない!)
ADMIN_DISCORD_ID = os.getenv("ADMIN_DISCORD_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

def is_admin(request: Request) -> bool:
    """管理者かどうか確認"""
    discord_id = request.session.get("discord_id")
    is_admin_authenticated = request.session.get("admin_authenticated", False)
    return discord_id == ADMIN_DISCORD_ID and is_admin_authenticated

@router.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """管理者ログインページ"""
    discord_id = request.session.get("discord_id")
    
    # Discord OAuth2でログインしていない場合
    if not discord_id:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # 管理者IDでない場合
    if discord_id != ADMIN_DISCORD_ID:
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    # すでに認証済みの場合
    if request.session.get("admin_authenticated"):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    # パスワード入力画面
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "discord_id": discord_id
    })

@router.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    """管理者パスワード認証"""
    discord_id = request.session.get("discord_id")
    
    if discord_id != ADMIN_DISCORD_ID:
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "discord_id": discord_id,
            "error": "パスワードが間違っています"
        })
    
    # 認証成功
    request.session["admin_authenticated"] = True
    return RedirectResponse(url="/admin/dashboard", status_code=302)

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """管理者ダッシュボード"""
    if not is_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    
    # 全プレイヤーデータ取得
    players_data = supabase_client.supabase.table("players").select("*").execute()
    players = players_data.data if players_data.data else []
    
    # 進行中のトレード取得
    trades_data = supabase_client.supabase.table("trades").select("*").eq("status", "pending").execute()
    trades = trades_data.data if trades_data.data else []
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "discord_id": request.session.get("discord_id"),
        "players": players,
        "trades": trades
    })

@router.post("/admin/ban-bot/{discord_id}")
async def ban_bot_user(request: Request, discord_id: str):
    """BOT利用禁止"""
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "bot_banned": True
    }).eq("discord_id", discord_id).execute()
    
    return {"message": f"Discord ID {discord_id} をBOT利用禁止にしました"}

@router.post("/admin/ban-web/{discord_id}")
async def ban_web_user(request: Request, discord_id: str):
    """Web利用禁止"""
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "web_banned": True
    }).eq("discord_id", discord_id).execute()
    
    return {"message": f"Discord ID {discord_id} をWeb利用禁止にしました"}

@router.post("/admin/unban-bot/{discord_id}")
async def unban_bot_user(request: Request, discord_id: str):
    """BOT利用禁止解除"""
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "bot_banned": False
    }).eq("discord_id", discord_id).execute()
    
    return {"message": f"Discord ID {discord_id} のBOT利用禁止を解除しました"}

@router.post("/admin/unban-web/{discord_id}")
async def unban_web_user(request: Request, discord_id: str):
    """Web利用禁止解除"""
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "web_banned": False
    }).eq("discord_id", discord_id).execute()
    
    return {"message": f"Discord ID {discord_id} のWeb利用禁止を解除しました"}

@router.post("/admin/cancel-trade/{trade_id}")
async def cancel_trade(request: Request, trade_id: int):
    """トレード強制キャンセル"""
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    # トレード情報取得
    trade = supabase_client.supabase.table("trades").select("*").eq("id", trade_id).single().execute()
    
    if not trade.data:
        raise HTTPException(status_code=404, detail="トレードが見つかりません")
    
    # 保留解除
    supabase_client.supabase.table("trade_holds").delete().eq("trade_id", trade_id).execute()
    
    # トレードステータスを cancelled に
    supabase_client.supabase.table("trades").update({
        "status": "cancelled"
    }).eq("id", trade_id).execute()
    
    return {"message": f"トレード ID {trade_id} を強制キャンセルしました"}

@router.get("/admin/player/{discord_id}", response_class=HTMLResponse)
async def view_player_data(request: Request, discord_id: str):
    """プレイヤーデータ詳細表示"""
    if not is_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    
    # プレイヤーデータ取得
    player_data = supabase_client.supabase.table("players").select("*").eq("discord_id", discord_id).single().execute()
    
    if not player_data.data:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")
    
    return templates.TemplateResponse("admin_player_detail.html", {
        "request": request,
        "discord_id": request.session.get("discord_id"),
        "player": player_data.data
    })
    
    
@router.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """管理者ログインページ"""
    discord_id = request.session.get("discord_id")
    
    # デバッグ用ログ
    print(f"セッションのDiscord ID: {discord_id}")
    print(f"環境変数のADMIN_DISCORD_ID: {ADMIN_DISCORD_ID}")
    print(f"一致: {discord_id == ADMIN_DISCORD_ID}")
    
    # Discord OAuth2でログインしていない場合
    if not discord_id:
        print("Discord IDがセッションにありません")
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # 管理者IDでない場合
    if discord_id != ADMIN_DISCORD_ID:
        print(f"管理者IDではありません: {discord_id} != {ADMIN_DISCORD_ID}")
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    # すでに認証済みの場合
    if request.session.get("admin_authenticated"):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    # パスワード入力画面
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "discord_id": discord_id
    })

@router.post("/admin/logout")
async def admin_logout(request: Request):
    """管理者ログアウト"""
    request.session["admin_authenticated"] = False
    return RedirectResponse(url="/", status_code=302)