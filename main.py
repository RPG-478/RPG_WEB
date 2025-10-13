import json
from typing import Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from routes import status, trade, auth

class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,  # ← 日本語そのまま出力
            separators=(",", ":")
        ).encode("utf-8")
# ---------------------

app = FastAPI(
    title="RPG BOT Web",
    version="1.0.0",
    default_response_class=UTF8JSONResponse  # ← 全APIのデフォルトに指定
)

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>RPG BOT Web — 起動成功</h1><p>SupabaseとBOT接続準備中...</p>"

# ルーター読み込み
app.include_router(status.router, tags=["status"])
app.include_router(trade.router, tags=["trade"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])