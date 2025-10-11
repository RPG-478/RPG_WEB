from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from routes import status

app = FastAPI()

app.include_router(status.router)

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>RPG BOT Web — 起動成功</h1><p>SupabaseとBOT接続準備中...</p>"