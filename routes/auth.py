import os
import secrets
import requests
from jose import jwt, JWTError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import asyncio
from datetime import datetime, timedelta

router = APIRouter()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
SECRET_KEY = os.getenv("SESSION_SECRET")

if not SECRET_KEY:
    raise ValueError("SESSION_SECRETの環境変数を設定してください。セキュリティ上、デフォルト値は使用できません。")

ALGORITHM = "HS256"
DISCORD_API_URL = "https://discord.com/api"

@router.get("/login")
async def login(response: Response):
    """Discord OAuth2認証ページへリダイレクト（CSRF保護付き）"""
    if not DISCORD_CLIENT_ID or not REDIRECT_URI:
        return JSONResponse(
            {"error": "Discord認証が設定されていません。環境変数を確認してください。"},
            status_code=500
        )

    state = secrets.token_urlsafe(32)
    state_expiry = datetime.utcnow() + timedelta(minutes=10)

    state_data = jwt.encode(
        {"state": state, "exp": state_expiry},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    auth_url = (
        f"{DISCORD_API_URL}/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
        f"&state={state}"
    )

    redirect_response = RedirectResponse(auth_url)
    redirect_response.set_cookie(
        key="oauth_state",
        value=state_data,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600
    )
    return redirect_response


@router.get("/callback")
async def callback(code: str, state: str, request: Request):
    """Discord OAuth2 コールバック - CSRF保護とレート制限対策済み"""

    # ↓↓↓ ここから追加 ↓↓↓
    from utils.security import get_client_ip
    import supabase_client

    client_ip = get_client_ip(request)

    # 1時間以内のOAuth2試行回数チェック (DoS対策)
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()

    oauth_attempts = supabase_client.supabase.table("oauth_attempts").select("*").eq(
        "ip_address", client_ip
    ).gte("created_at", one_hour_ago).execute()

    if oauth_attempts.data and len(oauth_attempts.data) >= 20:
        raise HTTPException(
            status_code=429,
            detail="OAuth2ログイン試行が多すぎます。1時間後に再試行してください。"
        )

    # OAuth2試行を記録
    supabase_client.supabase.table("oauth_attempts").insert({
        "ip_address": client_ip,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    # ↑↑↑ ここまで追加 ↑↑↑

    # 既存のコード (if not all([DISCORD_CLIENT_ID...]) から続く)
    if not all([DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, REDIRECT_URI]):
        return JSONResponse(
            {"error": "Discord認証設定が不完全です"},
            status_code=500
        )
    # ... 以下既存コード
async def callback(code: str, state: str, request: Request):
    """Discord OAuth2 コールバック - CSRF保護とレート制限対策済み"""
    if not all([DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, REDIRECT_URI]):
        return JSONResponse(
            {"error": "Discord認証設定が不完全です"},
            status_code=500
        )

    state_cookie = request.cookies.get("oauth_state")
    if not state_cookie:
        raise HTTPException(status_code=403, detail="認証状態が見つかりません")

    try:
        state_payload = jwt.decode(
            state_cookie,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True}
        )
        expected_state = state_payload.get("state")

        if not expected_state or expected_state != state:
            raise HTTPException(status_code=403, detail="無効なstateパラメータです")

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="認証リクエストの有効期限が切れました")
    except JWTError:
        raise HTTPException(status_code=403, detail="認証状態の検証に失敗しました")

    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    token_resp = None
    for attempt in range(3):
        try:
            token_resp = requests.post(
                f"{DISCORD_API_URL}/oauth2/token",
                data=token_data,
                headers=headers
            )
            token_resp.raise_for_status()
            break
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after else (2 ** attempt)
                await asyncio.sleep(wait_time)

                if attempt == 2:
                    return JSONResponse(
                        {"error": "レート制限により認証に失敗しました"},
                        status_code=429
                    )
            else:
                return JSONResponse(
                    {"error": f"Discord API Error: {e.response.status_code}"},
                    status_code=e.response.status_code
                )
        except requests.exceptions.RequestException as e:
            return JSONResponse(
                {"error": f"ネットワークエラー: {str(e)}"},
                status_code=500
            )

    if token_resp is None or not token_resp.ok:
        return JSONResponse(
            {"error": "アクセストークンの取得に失敗しました"},
            status_code=500
        )

    access_token = token_resp.json().get("access_token")
    if not access_token:
        return JSONResponse(
            {"error": "アクセストークンが見つかりません"},
            status_code=400
        )

    user_resp = requests.get(
        f"{DISCORD_API_URL}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_resp.raise_for_status()
    user_data = user_resp.json()

    expiration = datetime.utcnow() + timedelta(hours=24)
    token_payload = {
        "discord_id": user_data["id"],
        "exp": expiration
    }
    token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=86400
    )
    response.delete_cookie("oauth_state")
    return response


@router.get("/logout")
async def logout():
    """ログアウト（Cookie削除）"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response


@router.get("/me")
async def me(token: str = None):
    """ユーザー情報取得（デバッグ用）"""
    if not token:
        return JSONResponse({"error": "ログインしていません"}, status_code=401)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"status": "success", "discord_id": payload["discord_id"]}
    except Exception:
        return JSONResponse({"error": "無効なトークン"}, status_code=401)
