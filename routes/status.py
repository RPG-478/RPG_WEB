# routes/status.py
from fastapi import APIRouter, Query
from supabase_client import supabase

router = APIRouter()

@router.get("/status")
async def get_status(user_id: str = Query(..., description="ユーザーのDiscord ID")):
    try:
        response = supabase.table("players").select("*").eq("user_id", user_id).execute()
        data = response.data
        if not data:
            return {"error": "ユーザーが見つかりません"}
        return {"status": "success", "player": data[0]}
    except Exception as e:
        return {"error": str(e)}