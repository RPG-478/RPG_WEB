# utils/auth.py 
from fastapi import Request, HTTPException
from jose import jwt, JWTError
import os

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")  # 環境変数にしておく

def get_current_user(request: Request):
    token = request.cookies.get("session_token") 
    
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in.")

    try:
        # JWTのデコード
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        
        # routes/auth.py でエンコードしたキー名を使用
        discord_id: str = payload.get("discord_id") 
        
        if not discord_id:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
        
        return discord_id
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Token validation failed.")
