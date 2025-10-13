from fastapi import APIRouter, Request, Form, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import jwt, JWTError
import os
import supabase_client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 環境変数から取得
ADMIN_DISCORD_ID = os.getenv("ADMIN_DISCORD_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SESSION_SECRET")
ALGORITHM = "HS256"

def get_discord_id_from_token(session_token: str = None) -> str:
    """JWTトークンからDiscord IDを取得"""
    if not session_token:
        print("DEBUG: session_token が None です")
        return None
    try:
        payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
        discord_id = payload.get("discord_id")
        print(f"DEBUG: JWTペイロード = {payload}")
        print(f"DEBUG: discord_id = {discord_id}, type = {type(discord_id)}")
        return str(discord_id) if discord_id else None
    except JWTError as e:
        print(f"DEBUG: JWTデコードエラー - {e}")
        return None

def is_admin(discord_id: str, request: Request) -> bool:
    """管理者かどうか確認"""
    if not discord_id:
        return False
    admin_cookie = request.cookies.get("admin_authenticated")
    is_admin_auth = admin_cookie == "true"
    print(f"DEBUG: is_admin check - discord_id={discord_id}, ADMIN_DISCORD_ID={ADMIN_DISCORD_ID}, admin_auth={is_admin_auth}")
    return discord_id == ADMIN_DISCORD_ID and is_admin_auth

@router.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request, session_token: str = Cookie(None)):
    """管理者ログインページ"""
    discord_id = get_discord_id_from_token(session_token)
    
    # デバッグログ
    print(f"DEBUG: discord_id = {discord_id}, type = {type(discord_id)}")
    print(f"DEBUG: ADMIN_DISCORD_ID = {ADMIN_DISCORD_ID}, type = {type(ADMIN_DISCORD_ID)}")
    print(f"DEBUG: 一致? {discord_id == ADMIN_DISCORD_ID}")
    
    # Discord OAuth2でログインしていない場合
    if not discord_id:
        print("DEBUG: Discord IDが取得できませんでした")
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # 管理者IDでない場合
    if discord_id != ADMIN_DISCORD_ID:
        print(f"DEBUG: 管理者IDではありません")
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    # すでに認証済みの場合
    if request.cookies.get("admin_authenticated") == "true":
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    # パスワード入力画面
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "discord_id": discord_id
    })

@router.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...), session_token: str = Cookie(None)):
    """管理者パスワード認証"""
    discord_id = get_discord_id_from_token(session_token)
    
    if discord_id != ADMIN_DISCORD_ID:
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "discord_id": discord_id,
            "error": "パスワードが間違っています"
        })
    
    # 認証成功
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    response.set_cookie(
        key="admin_authenticated",
        value="true",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400  # 24時間
    )
    return response

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, session_token: str = Cookie(None)):
    """管理者ダッシュボード"""
    discord_id = get_discord_id_from_token(session_token)
    
    if not is_admin(discord_id, request):
        return RedirectResponse(url="/admin", status_code=302)
    
    # 全プレイヤーデータ取得
    players_data = supabase_client.supabase.table("players").select("*").execute()
    players = players_data.data if players_data.data else []
    
    # ========== デバッグログ追加 ==========
    print(f"========== デバッグ開始 ==========")
    print(f"プレイヤー数: {len(players)}")
    
    if players:
        print(f"最初のプレイヤー: {players[0]}")
        print(f"カラム名一覧: {list(players[0].keys())}")
        
        # user_id と discord_id の確認
        first_player = players[0]
        print(f"user_id の値: {first_player.get('user_id')}")
        print(f"discord_id の値: {first_player.get('discord_id')}")
    else:
        print("プレイヤーデータが0件です")
    
    print(f"========== デバッグ終了 ==========")
    # =====================================
    
    # 進行中のトレード取得
    trades_data = supabase_client.supabase.table("trades").select("*").eq("status", "pending").execute()
    trades = trades_data.data if trades_data.data else []
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "discord_id": discord_id,
        "players": players,
        "trades": trades
    })

@router.post("/admin/ban-bot/{discord_id}")
async def ban_bot_user(request: Request, discord_id: str, session_token: str = Cookie(None)):
    """BOT利用禁止"""
    admin_id = get_discord_id_from_token(session_token)
    if not is_admin(admin_id, request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "bot_banned": True
    }).eq("user_id", discord_id).execute()  # ← user_id に変更
    
    return {"message": f"Discord ID {discord_id} をBOT利用禁止にしました"}

@router.post("/admin/ban-web/{discord_id}")
async def ban_web_user(request: Request, discord_id: str, session_token: str = Cookie(None)):
    """Web利用禁止"""
    admin_id = get_discord_id_from_token(session_token)
    if not is_admin(admin_id, request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "web_banned": True
    }).eq("user_id", discord_id).execute()  # ← user_id に変更
    
    return {"message": f"Discord ID {discord_id} をWeb利用禁止にしました"}

@router.post("/admin/unban-bot/{discord_id}")
async def unban_bot_user(request: Request, discord_id: str, session_token: str = Cookie(None)):
    """BOT利用禁止解除"""
    admin_id = get_discord_id_from_token(session_token)
    if not is_admin(admin_id, request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "bot_banned": False
    }).eq("user_id", discord_id).execute()  # ← user_id に変更
    
    return {"message": f"Discord ID {discord_id} のBOT利用禁止を解除しました"}

@router.post("/admin/unban-web/{discord_id}")
async def unban_web_user(request: Request, discord_id: str, session_token: str = Cookie(None)):
    """Web利用禁止解除"""
    admin_id = get_discord_id_from_token(session_token)
    if not is_admin(admin_id, request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    supabase_client.supabase.table("players").update({
        "web_banned": False
    }).eq("user_id", discord_id).execute()  # ← user_id に変更
    
    return {"message": f"Discord ID {discord_id} のWeb利用禁止を解除しました"}

@router.post("/admin/cancel-trade/{trade_id}")
async def cancel_trade(request: Request, trade_id: int, session_token: str = Cookie(None)):
    """トレード強制キャンセル"""
    admin_id = get_discord_id_from_token(session_token)
    if not is_admin(admin_id, request):
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
async def view_player_data(request: Request, discord_id: str, session_token: str = Cookie(None)):
    """プレイヤーデータ詳細表示"""
    admin_id = get_discord_id_from_token(session_token)
    if not is_admin(admin_id, request):
        return RedirectResponse(url="/admin", status_code=302)
    
    # プレイヤーデータ取得
    player_data = supabase_client.supabase.table("players").select("*").eq("user_id", discord_id).single().execute()  # ← user_id に変更
    
    if not player_data.data:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")
    
    return templates.TemplateResponse("admin_player_detail.html", {
        "request": request,
        "discord_id": admin_id,
        "player": player_data.data
    })

@router.post("/admin/logout")
async def admin_logout():
    """管理者ログアウト"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("admin_authenticated")
    return response