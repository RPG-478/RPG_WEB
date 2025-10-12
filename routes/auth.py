# routes/auth.py
import os
import requests
from jose import jwt
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, JSONResponse

router = APIRouter()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")  # 例: https://rpg-web.onrender.com/callback
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"

@router.get("/login")
async def login():
    """Discord OAuth2認証ページへリダイレクト"""
    auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def callback(code: str):
    """Discord OAuth2 コールバック"""
    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # アクセストークン取得
    token_resp = requests.post("https://discord.com/api/oauth2/token", data=token_data, headers=headers)
    token_resp.raise_for_status()
    access_token = token_resp.json().get("access_token")

    # Discordユーザー情報取得
    user_resp = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_data = user_resp.json()

    # JWT発行してCookieに保存
    token = jwt.encode({"discord_id": user_data["id"]}, SECRET_KEY, algorithm=ALGORITHM)
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(key="token", value=token, httponly=True)
    return response

@router.get("/logout")
async def logout():
    """ログアウト（Cookie削除）"""
    response = RedirectResponse(url="/")
    response.delete_cookie("token")
    return response

@router.get("/me")
async def me(token: str = None):
    """Cookie内のJWTを確認（デバッグ用）"""
    if not token:
        return JSONResponse({"error": "ログインしていません"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"status": "success", "discord_id": payload["discord_id"]}
    except Exception:
        return {"error": "無効なトークンです"}