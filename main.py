# main.py
import json
from typing import Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from routes import status, trade, auth


app = FastAPI(
    title="RPG BOT Web",
    version="1.0.0", 
)

# ルートパスの定義 (HTMLResponseを使用)
@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>RPG BOT Web — 起動成功</h1><p>SupabaseとBOT接続準備中...</p>"

# ルーターの組み込み
# /status や /trade のルートは、デフォルト設定（UTF8JSONResponse）が適用
app.include_router(status.router, tags=["status"]) 
app.include_router(trade.router, tags=["trade"])   # tagsを追加してAPIを見やすく
app.include_router(auth.router, prefix="/auth", tags=["auth"])
