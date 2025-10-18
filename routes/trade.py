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
    item_names: list = Form(...),  # 複数選択対応
    sender_id: str = Depends(get_current_user)
):
    """トレード提案を作成 (ステップ①)"""
    try:
        sender_player = supabase_client.get_player(sender_id)
        if not sender_player:
            return JSONResponse(
                {"error": "送信者が見つかりません"},
                status_code=404
            )

        # アイテム所持確認
        inventory = sender_player.get("inventory", [])
        for item in item_names:
            if item not in inventory:
                return JSONResponse(
                    {"error": f"アイテム '{item}' を所持していません"},
                    status_code=400
                )

        receiver_player = supabase_client.get_player(receiver_id)
        if not receiver_player:
            return JSONResponse(
                {"error": "受信者が見つかりません"},
                status_code=404
            )

        # トレード提案作成
        trade = supabase_client.create_trade_proposal(
            sender_id, receiver_id, item_names
        )

        if trade:
            return RedirectResponse(url="/trade", status_code=303)
        else:
            return JSONResponse(
                {"error": "トレード提案の作成に失敗しました"},
                status_code=500
            )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@router.post("/trade/{trade_id}/receiver-respond")
async def receiver_respond(
    trade_id: int,
    action: str = Form(...),  # "accept" or "reject"
    item_names: list = Form(default=[]),  # 受信者のアイテム
    user_id: str = Depends(get_current_user)
):
    """受信者の応答 (ステップ②③)"""
    try:
        if action == "reject":
            # 拒否の場合
            success = supabase_client.reject_trade(trade_id)
            if success:
                return RedirectResponse(url="/trade", status_code=303)
            else:
                return JSONResponse(
                    {"error": "トレードの拒否に失敗しました"},
                    status_code=400
                )

        elif action == "accept":
            # 承認 + アイテム提示
            receiver_player = supabase_client.get_player(user_id)
            if not receiver_player:
                return JSONResponse(
                    {"error": "プレイヤーが見つかりません"},
                    status_code=404
                )

            # アイテム所持確認
            inventory = receiver_player.get("inventory", [])
            for item in item_names:
                if item not in inventory:
                    return JSONResponse(
                        {"error": f"アイテム '{item}' を所持していません"},
                        status_code=400
                    )

            # 受信者のアイテムを設定
            success = supabase_client.set_receiver_items(trade_id, item_names)
            if success:
                return RedirectResponse(url="/trade", status_code=303)
            else:
                return JSONResponse(
                    {"error": "アイテムの設定に失敗しました"},
                    status_code=400
                )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@router.post("/trade/{trade_id}/sender-approve")
async def sender_approve(
    trade_id: int,
    action: str = Form(...),  # "approve" or "reject"
    user_id: str = Depends(get_current_user)
):
    """送信者の最終承認 (ステップ④)"""
    try:
        if action == "reject":
            success = supabase_client.reject_trade(trade_id)
            if success:
                return RedirectResponse(url="/trade", status_code=303)
            else:
                return JSONResponse(
                    {"error": "トレードのキャンセルに失敗しました"},
                    status_code=400
                )

        elif action == "approve":
            # トレード完了処理
            success = supabase_client.complete_trade(trade_id)
            if success:
                return RedirectResponse(url="/trade", status_code=303)
            else:
                return JSONResponse(
                    {"error": "トレードの完了に失敗しました"},
                    status_code=400
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
    """トレードページ"""
    player = supabase_client.get_player(discord_id)
    if not player:
        return RedirectResponse(url="/dashboard")

    # 自分に関連するトレードを取得
    my_trades = supabase_client.get_my_trades(discord_id)
    trade_history = supabase_client.get_trade_history(discord_id)

    # 利用可能なインベントリ
    available_inventory = supabase_client.get_available_inventory(discord_id)
    held_items = supabase_client.get_held_items(discord_id)

    return templates.TemplateResponse("trade.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "available_inventory": available_inventory,
        "held_items": held_items,
        "my_trades": my_trades,  # 全てのトレード (状態別)
        "trade_history": trade_history
    })