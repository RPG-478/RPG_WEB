import json
from typing import Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from routes import status, trade

# 日本語文字化け対策のためのカスタムレスポンスクラスを定義
# JSONResponseを継承し、日本語がエスケープされないようにする
class UTF8JSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        # ensure_ascii=False で日本語をそのまま出力し、UTF-8でエンコード
        return json.dumps(
            content,
            ensure_ascii=False,  
            indent=None,
            separators=(",", ":")
        ).encode("utf-8")


# FastAPIの初期化
# JSONを返すAPIには、このカスタムレスポンスをデフォルトで適用する
app = FastAPI(
    title="RPG BOT Web",
    version="1.0.0",
    # 日本語対応のJSONResponseをデフォルトに
    default_response_class=UTF8JSONResponse 
)

# ルートパスの定義 (HTMLResponseを使用)
# ルートパスは、HTMLResponseを使用
@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>RPG BOT Web — 起動成功</h1><p>SupabaseとBOT接続準備中...</p>"


# ルーターの組み込み
# /status や /trade のルートは、デフォルト設定（UTF8JSONResponse）が適用
app.include_router(status.router)
app.include_router(trade.router)
