from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from utils.auth import get_current_user
import supabase_client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.post("/trade/request")
async def trade_request(
    receiver_id: str = Form(...),
    item_name: str = Form(...),
    sender_id: str = Depends(get_current_user)
):
    """トレードリクエストを作成"""
    try:
        sender_player = supabase_client.get_player(sender_id)
        if not sender_player:
            return JSONResponse(
                {"error": "送信者が見つかりません"},
                status_code=404
            )
        
        inventory = sender_player.get("inventory", [])
        if item_name not in inventory:
            return JSONResponse(
                {"error": f"アイテム '{item_name}' を所持していません"},
                status_code=400
            )
        
        receiver_player = supabase_client.get_player(receiver_id)
        if not receiver_player:
            return JSONResponse(
                {"error": "受信者が見つかりません"},
                status_code=404
            )
        
        trade = supabase_client.create_trade_request(
            sender_id, receiver_id, item_name
        )
        
        if trade:
            return RedirectResponse(url="/trade", status_code=303)
        else:
            return JSONResponse(
                {"error": "トレードの作成に失敗しました"},
                status_code=500
            )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@router.get("/trade/history")
async def trade_history(user_id: str = Depends(get_current_user)):
    """トレード履歴API"""
    try:
        history = supabase_client.get_trade_history(user_id)
        return JSONResponse(
            {"status": "success", "history": history},
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@router.get("/trade", response_class=HTMLResponse)
async def trade_page(request: Request, discord_id: str = Depends(get_current_user)):
    """トレードページ(保留機能対応版)"""
    player = supabase_client.get_player(discord_id)
    if not player:
        return RedirectResponse(url="/dashboard")
    
    pending_trades = supabase_client.get_pending_trades(discord_id)
    trade_history = supabase_client.get_trade_history(discord_id)
    
    # 利用可能なインベントリ(保留中を除く)を取得
    available_inventory = supabase_client.get_available_inventory(discord_id)
    held_items = supabase_client.get_held_items(discord_id)
    
    return templates.TemplateResponse("trade.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "available_inventory": available_inventory,  # 保留中を除いたインベントリ
        "held_items": held_items,  # 保留中のアイテム
        "pending_trades": pending_trades,
        "trade_history": trade_history
    })

@router.post("/trade/{trade_id}/approve")
async def approve_trade(
    trade_id: int,
    user_id: str = Depends(get_current_user)
):
    """トレードを承認"""
    try:
        success = supabase_client.approve_trade(trade_id)
        if success:
            return RedirectResponse(url="/trade", status_code=303)
        else:
            return JSONResponse(
                {"error": "トレードの承認に失敗しました"},
                status_code=400
            )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@router.post("/trade/{trade_id}/reject")
async def reject_trade(
    trade_id: int,
    user_id: str = Depends(get_current_user)
):
    """トレードを拒否"""
    try:
        success = supabase_client.reject_trade(trade_id)
        if success:
            return RedirectResponse(url="/trade", status_code=303)
        else:
            return JSONResponse(
                {"error": "トレードの拒否に失敗しました"},
                status_code=400
            )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )