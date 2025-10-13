import json
from typing import Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from routes import status, trade, auth
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,  # ← 日本語そのまま出力
            separators=(",", ":")
        ).encode("utf-8")

app = FastAPI(
    title="RPG BOT Web",
    version="1.0.0",
    default_response_class=UTF8JSONResponse
)

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>RPG BOT Web — 起動成功</h1><p>SupabaseとBOT接続準備中...</p>"

# ルーター読み込み
app.include_router(status.router, tags=["status"])
app.include_router(trade.router, tags=["trade"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])


# 圧縮とCORS許可（Render対策のおまけ）
app.add_middleware(GZipMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Renderが勝手にJSONをダウンロード扱いするのを修正
@app.middleware("http")
async def force_json_headers(request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        if "content-disposition" in response.headers:
            del response.headers["content-disposition"]
    return response