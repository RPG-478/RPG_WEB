import json
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timedelta
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
import os

from routes import status, trade, auth, legal, admin, trade_board, dm

class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            separators=(",", ":")
        ).encode("utf-8")

# グローバルレート制限 (メモリベース)
rate_limit_storage = defaultdict(list)

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 管理画面は別のセキュリティで守られているのでスキップ
        if request.url.path.startswith("/admin"):
            return await call_next(request)

        # IPアドレス取得
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")

        current_time = datetime.utcnow()

        # 1分以内のリクエスト数をカウント
        one_minute_ago = current_time - timedelta(minutes=1)
        rate_limit_storage[client_ip] = [
            timestamp for timestamp in rate_limit_storage[client_ip]
            if timestamp > one_minute_ago
        ]

        # レート制限チェック (1分間に30リクエスト)
        if len(rate_limit_storage[client_ip]) >= 30:
            from fastapi.templating import Jinja2Templates
            templates = Jinja2Templates(directory="templates")
            return templates.TemplateResponse(
                "rate_limit.html",
                {"request": request},
                status_code=429
            )

        # リクエスト記録
        rate_limit_storage[client_ip].append(current_time)

        return await call_next(request)

# FastAPIアプリ作成
app = FastAPI(
    title="RPG BOT Web",
    version="1.0.0",
    default_response_class=UTF8JSONResponse
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# アプリにレート制限ミドルウェアを追加
app.add_middleware(RateLimitMiddleware)

# SessionMiddleware を追加
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "your-secret-key-here-change-in-production")
)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """トップページ"""
    return templates.TemplateResponse("index.html", {
        "request": request
    })

# ルーター登録
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(status.router, tags=["status"])
app.include_router(trade.router, tags=["trade"])
app.include_router(legal.router, tags=["legal"])
app.include_router(trade_board.router, tags=["trade_board"])
app.include_router(dm.router, tags=["dm"])
app.include_router(admin.router, tags=["admin"])

app.add_middleware(GZipMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def force_json_headers(request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        if "content-disposition" in response.headers:
            del response.headers["content-disposition"]
    return response

from fastapi import BackgroundTasks
import supabase_client
import asyncio

@app.on_event("startup")
async def startup_event():
    """アプリ起動時に期限切れ保留をクリーンアップ"""
    supabase_client.cleanup_expired_holds()
    # トレード投稿のクリーンアップも追加
    supabase_client.cleanup_expired_trade_posts()

# 定期的にクリーンアップ(オプション)
async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  # 1時間ごと
        supabase_client.cleanup_expired_holds()
        supabase_client.cleanup_expired_trade_posts()

@app.on_event("startup")
async def start_periodic_tasks():
    asyncio.create_task(periodic_cleanup())