import json
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
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
        # ヘルスチェックと管理画面はスキップ
        if request.url.path in ["/health", "/"] or request.url.path.startswith("/admin"):
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

# ========================================
# ヘルスチェックエンドポイント (UptimeRobot対応)
# ========================================

@app.get("/health", response_class=PlainTextResponse)
@app.head("/health", response_class=PlainTextResponse)
async def health_check():
    """
    ヘルスチェックエンドポイント
    UptimeRobotやRenderの監視に使用
    HEADとGETリクエストの両方に対応
    """
    return "OK"

@app.head("/")
async def root_head():
    """
    ルートパスのHEADリクエスト対応
    一部の監視ツールはルートパスを使用する
    """
    return PlainTextResponse("OK", status_code=200)

# ========================================
# トップページ
# ========================================

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

# スタートアップイベント（Supabase接続時のみ有効）
@app.on_event("startup")
async def startup_event():
    """アプリ起動時の処理"""
    print("=" * 50)
    print("✅ RPG BOT Web サーバー起動完了")
    print("📍 ヘルスチェックエンドポイント: /health")
    print("📍 ルートパス: /")
    print("=" * 50)
    
    # 環境変数チェック
    required_env = ["SUPABASE_URL", "SUPABASE_KEY", "SESSION_SECRET"]
    missing_env = [env for env in required_env if not os.getenv(env)]
    
    if missing_env:
        print(f"⚠️  未設定の環境変数: {', '.join(missing_env)}")
        print("⚠️  データベース機能は利用できません")
        print("💡 Render.comデプロイ時は環境変数を設定してください")
    else:
        # Supabase設定がある場合のみクリーンアップを実行
        try:
            import supabase_client
            if supabase_client.get_supabase_client() is not None:
                supabase_client.cleanup_expired_holds()
                supabase_client.cleanup_expired_trade_posts()
                print("✅ 期限切れデータのクリーンアップ完了")
        except Exception as e:
            print(f"⚠️  Supabaseクリーンアップエラー: {e}")
    
    print("=" * 50)

# 定期的にクリーンアップ(オプション)
import asyncio

async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  # 1時間ごと
        try:
            import supabase_client
            supabase_client.cleanup_expired_holds()
            supabase_client.cleanup_expired_trade_posts()
        except Exception as e:
            print(f"定期クリーンアップエラー: {e}")

@app.on_event("startup")
async def start_periodic_tasks():
    try:
        asyncio.create_task(periodic_cleanup())
    except Exception as e:
        print(f"定期タスク起動エラー: {e}")
