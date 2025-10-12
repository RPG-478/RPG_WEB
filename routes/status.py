# routes/status.py

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse # ★ JSONResponse をインポート
from auth import get_current_user   

router = APIRouter()

@router.get("/status")
async def get_user_status(discord_id: str = Depends(get_current_user)):
    """ログインユーザーのステータスを取得"""
    
    return JSONResponse(
        content={
            "status": "success",
            "message": "ログイン済みです", 
            "discord_id": discord_id
        },
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(discord_id: str = Depends(get_current_user)):
    """ユーザーがログイン後に到達するページ"""
    return f"""
    <h1>ダッシュボードへようこそ！</h1>
    <p>あなたのDiscord ID: {discord_id}</p>
    <p><a href="/auth/logout">ログアウト</a></p>
    <p><a href="/status">ステータス確認API</a></p>
    """
