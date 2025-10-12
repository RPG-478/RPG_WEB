# routes/auth.py
import os
import requests
from jose import jwt
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, JSONResponse
import asyncio

router = APIRouter()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"

DISCORD_API_URL = "https://discord.com/api"


@router.get("/login")
async def login():
    """Discord OAuth2認証ページへリダイレクト"""
    auth_url = (
        f"{DISCORD_API_URL}/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(code: str):
    """Discord OAuth2 コールバック - レート制限対策済み"""
    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # 1. アクセストークン取得 (レート制限対策のリトライロジックを導入)
    token_resp = None
    for attempt in range(3): # 最大3回試行
        try:
            token_resp = requests.post(f"{DISCORD_API_URL}/oauth2/token", data=token_data, headers=headers)
            token_resp.raise_for_status()  # 200番台以外はここで例外発生
            break # 成功したらループを抜ける
        except requests.exceptions.HTTPError as e:
            # 429 Too Many Requests (レート制限) の場合
            if e.response.status_code == 429:
                # Discordが "Retry-After" ヘッダーを提供していれば、その時間待つ
                retry_after = e.response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after else (2 ** attempt) # 指示がなければ、指数関数的に待機時間を増やす (1, 2, 4秒)
                
                # FastAPIのイベントループを使って非同期的に待機する
                await asyncio.sleep(wait_time) 
                
                if attempt == 2: # 3回目の試行も失敗したら
                    return JSONResponse({"error": "Rate limit exceeded after multiple retries."}, status_code=429)
            else:
                # その他のHTTPエラー (例: 400 Bad Requestなど)
                return JSONResponse({"error": f"Discord API Error: {e.response.status_code}", "details": e.response.text}, status_code=e.response.status_code)
        except requests.exceptions.RequestException as e:
            # ネットワークエラーなどの場合
            return JSONResponse({"error": f"Network Error: {e}"}, status_code=500)


    if token_resp is None or not token_resp.ok:
        # 3回の試行後も失敗した場合
        return JSONResponse({"error": "Failed to get access token after all retries"}, status_code=500)

    access_token = token_resp.json().get("access_token")
    if not access_token:
        return JSONResponse({"error": "Access token is missing in response"}, status_code=400)


    # 2. Discordユーザー情報取得
    user_resp = requests.get(
        f"{DISCORD_API_URL}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_resp.raise_for_status() 
    user_data = user_resp.json()
    
    # 3. JWT発行
    token = jwt.encode({"discord_id": user_data["id"]}, SECRET_KEY, algorithm=ALGORITHM)
    
    # 4. Cookieに保存して /dashboard へリダイレクト
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="session_token", value=token, httponly=True)
    return response


@router.get("/logout")
async def logout():
    """ログアウト（Cookie削除）"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response


@router.get("/me")
async def me(token: str = None):
    if not token:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"status": "success", "discord_id": payload["discord_id"]}
    except Exception:
        return JSONResponse({"error": "Invalid token"}, status_code=401)
