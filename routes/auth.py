# routes/auth.py
import os
import requests
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse

router = APIRouter()

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

# DiscordのOAuth2認可エンドポイント
DISCORD_API = "https://discord.com/api"

@router.get("/login")
async def login():
    """Discordログインページにリダイレクト"""
    return RedirectResponse(
        f"{DISCORD_API}/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope=identify"
    )

@router.get("/callback")
async def callback(request: Request):
    """Discord OAuth2 コールバック"""
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "コードがありません"})

    # アクセストークン取得
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_resp = requests.post(f"{DISCORD_API}/oauth2/token", data=data, headers=headers)
    token_data = token_resp.json()

    if "access_token" not in token_data:
        return JSONResponse({"error": "トークン取得失敗", "details": token_data})

    access_token = token_data["access_token"]

    # Discordユーザー情報を取得
    user_resp = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_data = user_resp.json()

    # テスト段階では結果をそのまま返す
    return JSONResponse({
        "status": "success",
        "user": user_data
    })