from fastapi import APIRouter, Request, Form, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jose import jwt, JWTError
from passlib.hash import argon2
import os
import httpx
from datetime import datetime
import supabase_client
from utils.security import (
    check_account_lock,
    check_safe_mode_trigger,
    activate_safe_mode,
    is_safe_mode_active,
    record_login_attempt,
    get_client_ip
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 環境変数から取得
ADMIN_DISCORD_ID = os.getenv("ADMIN_DISCORD_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
RECOVERY_PASSWORD = os.getenv("RECOVERY_PASSWORD")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SECRET_KEY = os.getenv("SESSION_SECRET")
ALGORITHM = "HS256"

def get_discord_id_from_token(session_token: str = None) -> str:
    """JWTトークンからDiscord IDを取得"""
    if not session_token:
        return None
    try:
        payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
        discord_id = payload.get("discord_id")
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
    return discord_id == ADMIN_DISCORD_ID and is_admin_auth

def initialize_recovery_password():
    """初回起動時にRECOVERY_PASSWORDをArgon2ハッシュ化してDBに保存"""
    try:
        if not RECOVERY_PASSWORD:
            print("⚠️ RECOVERY_PASSWORD環境変数が設定されていません")
            return
        
        status = supabase_client.supabase.table("system_status").select("*").eq("id", 1).single().execute()
        
        if status.data and not status.data.get("recovery_password_hash"):
            # ハッシュ化して保存
            hashed = argon2.hash(RECOVERY_PASSWORD)
            supabase_client.supabase.table("system_status").update({
                "recovery_password_hash": hashed
            }).eq("id", 1).execute()
            print("✅ 復旧パスワードをArgon2ハッシュ化してDBに保存しました")
    except Exception as e:
        print(f"Error initializing recovery password: {e}")

# アプリ起動時に実行
initialize_recovery_password()

async def send_discord_alert(message: str):
    """Discord Webhookで通知を送信"""
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK_URL, json={
                "content": f"🚨 **セキュリティアラート**\n{message}"
            })
    except Exception as e:
        print(f"Error sending Discord alert: {e}")

@router.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request, session_token: str = Cookie(None)):
    """管理者ログインページ"""
    # SAFE_MODEチェック
    if is_safe_mode_active():
        return RedirectResponse(url="/admin/recovery", status_code=302)
    
    discord_id = get_discord_id_from_token(session_token)
    
    # Discord OAuth2でログインしていない場合
    if not discord_id:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    # 管理者IDでない場合
    if discord_id != ADMIN_DISCORD_ID:
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    # アカウントロックチェック
    lock_status = check_account_lock(discord_id)
    if lock_status["locked"]:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "discord_id": discord_id,
            "error": f"アカウントがロックされています。解除時刻: {lock_status['unlock_at']}"
        })
    
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
    # SAFE_MODEチェック
    if is_safe_mode_active():
        return RedirectResponse(url="/admin/recovery", status_code=302)
    
    discord_id = get_discord_id_from_token(session_token)
    client_ip = get_client_ip(request)
    
    if discord_id != ADMIN_DISCORD_ID:
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    # アカウントロックチェック
    lock_status = check_account_lock(discord_id)
    if lock_status["locked"]:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "discord_id": discord_id,
            "error": f"アカウントがロックされています。解除時刻: {lock_status['unlock_at']}"
        })
    
    # パスワード検証
    if password != ADMIN_PASSWORD:
        # ログイン失敗を記録
        record_login_attempt(discord_id, client_ip, False)
        
        # SAFE_MODE発動チェック
        if check_safe_mode_trigger():
            activate_safe_mode("複数IPから5回以上のログイン失敗を検出")
            await send_discord_alert(f"🚨 SAFE_MODE発動!\n複数IPから攻撃を検出しました。\n時刻: {datetime.utcnow().isoformat()}")
            return RedirectResponse(url="/admin/recovery", status_code=302)
        
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "discord_id": discord_id,
            "error": "パスワードが間違っています"
        })
    
    # ログイン成功を記録
    record_login_attempt(discord_id, client_ip, True)
    
    # 認証成功
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    response.set_cookie(
        key="admin_authenticated",
        value="true",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600  # 1時間
    )
    return response

@router.get("/admin/recovery", response_class=HTMLResponse)
async def recovery_page(request: Request, session_token: str = Cookie(None)):
    """復旧ページ"""
    discord_id = get_discord_id_from_token(session_token)
    
    # Discord OAuth2でログインしていない場合
    if not discord_id:
        return templates.TemplateResponse("system_locked.html", {
            "request": request,
            "error": "Discord OAuth2認証が必要です",
            "needs_oauth": True
        })
    
    # 管理者IDでない場合
    if discord_id != ADMIN_DISCORD_ID:
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    return templates.TemplateResponse("system_locked.html", {
        "request": request,
        "discord_id": discord_id
    })

@router.post("/admin/recovery")
async def recovery_unlock(request: Request, recovery_password: str = Form(...), session_token: str = Cookie(None)):
    """システム復旧処理"""
    discord_id = get_discord_id_from_token(session_token)
    client_ip = get_client_ip(request)
    
    # Discord OAuth2認証チェック
    if discord_id != ADMIN_DISCORD_ID:
        await send_discord_alert(f"❌ 復旧失敗: 不正なDiscord ID\nIP: {client_ip}\n時刻: {datetime.utcnow().isoformat()}")
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    # レート制限チェック (1時間に3回)
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    recent_attempts = supabase_client.supabase.table("recovery_attempts").select("*").eq(
        "ip_address", client_ip
    ).gte("created_at", one_hour_ago).execute()
    
    if recent_attempts.data and len(recent_attempts.data) >= 3:
        await send_discord_alert(f"⚠️ 復旧試行レート制限超過\nIP: {client_ip}\n時刻: {datetime.utcnow().isoformat()}")
        return templates.TemplateResponse("system_locked.html", {
            "request": request,
            "discord_id": discord_id,
            "error": "復旧試行の回数制限に達しました (1時間に3回まで)"
        })
    
    # 復旧パスワード検証 (Argon2)
    try:
        status = supabase_client.supabase.table("system_status").select("*").eq("id", 1).single().execute()
        stored_hash = status.data.get("recovery_password_hash")
        
        if not stored_hash or not argon2.verify(recovery_password, stored_hash):
            # 失敗を記録
            supabase_client.supabase.table("recovery_attempts").insert({
                "ip_address": client_ip,
                "discord_id": discord_id,
                "success": False,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            await send_discord_alert(f"❌ 復旧失敗: パスワード不一致\nDiscord ID: {discord_id}\nIP: {client_ip}\n時刻: {datetime.utcnow().isoformat()}")
            
            return templates.TemplateResponse("system_locked.html", {
                "request": request,
                "discord_id": discord_id,
                "error": "復旧パスワードが間違っています"
            })
        
        # 成功を記録
        supabase_client.supabase.table("recovery_attempts").insert({
            "ip_address": client_ip,
            "discord_id": discord_id,
            "success": True,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        
        # SAFE_MODE解除
        supabase_client.supabase.table("system_status").update({
            "is_safe_mode": False,
            "locked_at": None,
            "locked_reason": None
        }).eq("id", 1).execute()
        
        await send_discord_alert(f"✅ システム復旧成功\nDiscord ID: {discord_id}\nIP: {client_ip}\n時刻: {datetime.utcnow().isoformat()}")
        
        return RedirectResponse(url="/admin", status_code=302)
        
    except Exception as e:
        print(f"Error in recovery: {e}")
        await send_discord_alert(f"⚠️ 復旧処理エラー\nエラー: {str(e)}\n時刻: {datetime.utcnow().isoformat()}")
        raise HTTPException(status_code=500, detail="復旧処理に失敗しました")

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, session_token: str = Cookie(None)):
    """管理者ダッシュボード"""
    discord_id = get_discord_id_from_token(session_token)
    
    if not is_admin(discord_id, request):
        return RedirectResponse(url="/admin", status_code=302)
    
    # 全プレイヤーデータ取得
    players_data = supabase_client.supabase.table("players").select("*").execute()
    players = players_data.data if players_data.data else []
    
    # 進行中のトレード取得
    trades_data = supabase_client.supabase.table("trades").select("*").eq("status", "pending").execute()
    trades = trades_data.data if trades_data.data else []
    
    # 管理者ログ取得 (最新20件)
    admin_logs_data = supabase_client.supabase.table("admin_logs").select("*").order("created_at", desc=True).limit(20).execute()
    admin_logs = admin_logs_data.data if admin_logs_data.data else []
    
    # BAN履歴取得 (最新20件)
    ban_history_data = supabase_client.supabase.table("ban_history").select("*").order("banned_at", desc=True).limit(20).execute()
    ban_history = ban_history_data.data if ban_history_data.data else []
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "discord_id": discord_id,
        "players": players,
        "trades": trades,
        "admin_logs": admin_logs,
        "ban_history": ban_history
    })

@router.post("/admin/ban-bot/{discord_id}")
async def ban_bot_user(request: Request, discord_id: str, reason: str = Form(...), session_token: str = Cookie(None)):
    """BOT利用禁止 (理由必須)"""
    admin_id = get_discord_id_from_token(session_token)
    if not is_admin(admin_id, request):
        raise HTTPException(status_code=403, detail="管理者権限がありません")
    
    client_ip = get_client_ip(request)
    
    # BANを実行
    supabase_client.supabase.table("players").update({
        "bot_banned": True
    }).eq("user_id", discord_id).execute()
    
    # BAN履歴を記録
    supabase_client.supabase.table("ban_history").insert({
        "user_id": discord_id,
        "ban_type": "bot",
        "reason": reason,
        "banned_by": admin_id,
        "banned_at": datetime.utcnow().isoformat(),
        "is_active": True
    }).execute()
    
    # 管理者ログを記録
    supabase_client.supabase.table("admin_logs").insert({
        "admin_id": admin_id,
        "action": "ban_bot",
        "target_id": discord_id,
        "reason": reason,
        "ip_address": client_ip,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    
    return JSONResponse({"message": f"Discord ID {discord_id} をBOT利用禁止にしました"})

# 同様に unban_bot, ban_web, unban_web も修正...
# (次のメッセージで提示します)

@router.post("/admin/logout")
async def admin_logout():
    """管理者ログアウト"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("admin_authenticated")
    return response