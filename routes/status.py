# routes/status.py （新規作成または修正）

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
# utils/auth.py から認証ガード関数をインポート
from utils.auth import get_current_user 

router = APIRouter()

@router.get("/status")
async def get_user_status(discord_id: str = Depends(get_current_user)):
    """ログインユーザーのステータスを取得"""
    
    # ★ ログインしていない場合:
    # get_current_userがHTTPExceptionを発生させるため、この関数は実行されず、
    # 401エラーが返る。

    # ★ ログイン済みの場合:
    # Supabaseからユーザーデータを取得する処理をここに追加
    # 例: player_data = await supabase_client.get_player_data(discord_id)

    # 応答
    return JSONResponse({
        "status": "success",
        "message": "ログイン済みです", # ★ 文字化け回避のため日本語はJSONResponseで
        "discord_id": discord_id
        # "player_data": player_data 
    })
