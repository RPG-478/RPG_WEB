import json
from typing import Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from routes import status, trade, auth

class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            separators=(",", ":")
        ).encode("utf-8")

app = FastAPI(
    title="RPG BOT Web",
    version="1.0.0",
    default_response_class=UTF8JSONResponse
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RPG BOT Web</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <div class="text-center">
                <h1 class="display-4">RPG BOT Web</h1>
                <p class="lead">Discord RPGã²ã¼ã ã®Webç®¡çã·ã¹ãã </p>
                <hr class="my-4">
                <p>Supabaseé£æºæºåå®äºãDiscord OAuthã§ã­ã°ã¤ã³ãã¦ãã ããã</p>
                <a href="/auth/login" class="btn btn-primary btn-lg">Discordã§ã­ã°ã¤ã³</a>
            </div>
        </div>
    </body>
    </html>
    """

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(status.router, tags=["status"])
app.include_router(trade.router, tags=["trade"])

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
    
from fastapi import FastAPI, BackgroundTasks
import supabase_client

@app.on_event("startup")
async def startup_event():
    """アプリ起動時に期限切れ保留をクリーンアップ"""
    supabase_client.cleanup_expired_holds()

# 定期的にクリーンアップ(オプション)
import asyncio

async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  # 1時間ごと
        supabase_client.cleanup_expired_holds()

@app.on_event("startup")
async def start_periodic_tasks():
    asyncio.create_task(periodic_cleanup())
