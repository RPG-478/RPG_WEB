# utils/auth.py
from fastapi import Request, HTTPException
from jose import jwt, JWTError
import os

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")  # 環境変数にしておく

def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="ログインしていません。")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="無効なトークン。")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="トークンの検証に失敗しました。")