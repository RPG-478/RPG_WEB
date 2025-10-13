# routes/trade.py
from fastapi import APIRouter, Query
from supabase_client import supabase
from datetime import datetime

router = APIRouter()

@router.post("/trade/request")
async def trade_request(sender_id: str = Query(...), receiver_id: str = Query(...), item_name: str = Query(...)):
    try:
        trade_data = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "item_name": item_name,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("trades").insert(trade_data).execute()
        return {"status": "success", "trade": response.data}
    except Exception as e:
        return {"error": str(e)}

@router.get("/trade/history")
async def trade_history(user_id: str = Query(...)):
    try:
        response = supabase.table("trades").select("*").or_(f"sender_id.eq.{user_id},receiver_id.eq.{user_id}").execute()
        return {"status": "success", "history": response.data}
    except Exception as e:
        return {"error": str(e)}
        

@router.get("/trade")
async def trade_page(request: Request, discord_id: str = Depends(get_current_user)):
    """認証後、トレードページをレンダリングし、必要なデータを渡す"""
    
    # Supabaseから必要なデータを取得
    player = supabase_client.get_player(discord_id)
    pending_trades = supabase_client.get_pending_trades(discord_id)
    trade_history = supabase_client.get_trade_history(discord_id)
    
    return templates.TemplateResponse("trade.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "pending_trades": pending_trades,
        "trade_history": trade_history
    })
