# routes/status.py （新規作成または修正）

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
# utils/auth.py から認証ガード関数をインポート
import auth

get_current_user = auth.get_current_user

router = APIRouter()

@router.get("/status")
async def get_user_status(discord_id: str = Depends(get_current_user)):
    """ログインユーザーのステータスを取得"""
    
    return JSONResponse({
        "status": "success",
        "message": "ログイン済みです", # 文字化け回避のため日本語はJSONResponseで
        "discord_id": discord_id
        # "player_data": player_data 
    })

from fastapi.responses import HTMLResponse

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(discord_id: str = Depends(get_current_user)):
    """ユーザーがログイン後に到達するページ"""
    
    # ログインしていない場合は get_current_user によって401

    return f"""
    <h1>ダッシュボードへようこそ！</h1>
    <p>あなたのDiscord ID: {discord_id}</p>
    <p><a href="/auth/logout">ログアウト</a></p>
    <p><a href="/status">ステータス確認API</a></p>
    """
