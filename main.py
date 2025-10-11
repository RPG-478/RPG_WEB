from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>RPG BOT Web — 起動成功</h1><p>SupabaseとBOT接続準備中...</p>"