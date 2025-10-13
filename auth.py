from fastapi import Request, HTTPException
from jose import jwt, JWTError
import os

SECRET_KEY = os.getenv("SESSION_SECRET")

if not SECRET_KEY:
    raise ValueError("SESSION_SECRETの環境変数を設定してください。セキュリティ上、デフォルト値は使用できません。")

def get_current_user(request: Request):
    """認証済みユーザーのDiscord IDを取得"""
    token = request.cookies.get("session_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="ログインが必要です")

    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=["HS256"],
            options={"verify_exp": True}
        )
        discord_id: str = payload.get("discord_id")
        
        if not discord_id:
            raise HTTPException(status_code=401, detail="無効なトークンです")
        
        return discord_id
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="セッションの有効期限が切れました。再度ログインしてください")
    except JWTError:
        raise HTTPException(status_code=401, detail="トークンの検証に失敗しました")
