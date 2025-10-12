# routes/status.py
from fastapi import APIRouter, Depends
from supabase_client import supabase
from auth import get_current_user

router = APIRouter()

@router.get("/status")
async def get_status(discord_id: str = Depends(get_current_user)):
    response = supabase.table("players").select("*").eq("user_id", discord_id).execute()
    data = response.data
    if not data:
        return {"error": "ユーザーが見つかりません"}
    return {"status": "success", "player": data[0]}