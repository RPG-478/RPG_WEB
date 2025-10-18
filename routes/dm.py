from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from utils.auth import get_current_user
import supabase_client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dm/inbox", response_class=HTMLResponse)
async def dm_inbox(request: Request, discord_id: str = Depends(get_current_user)):
    """受信箱"""
    player = supabase_client.get_player(discord_id)
    if not player:
        return RedirectResponse(url="/dashboard")

    # 受信したメッセージを取得
    received = supabase_client.get_received_messages(discord_id)

    # 未読件数
    unread_count = supabase_client.get_unread_count(discord_id)

    return templates.TemplateResponse("dm_inbox.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "messages": received,
        "unread_count": unread_count
    })


@router.get("/dm/sent", response_class=HTMLResponse)
async def dm_sent(request: Request, discord_id: str = Depends(get_current_user)):
    """送信箱"""
    player = supabase_client.get_player(discord_id)
    if not player:
        return RedirectResponse(url="/dashboard")

    # 送信したメッセージを取得
    sent = supabase_client.get_sent_messages(discord_id)

    return templates.TemplateResponse("dm_sent.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "messages": sent
    })


@router.get("/dm/send", response_class=HTMLResponse)
async def dm_send_page(request: Request, receiver_id: str = None, discord_id: str = Depends(get_current_user)):
    """DM送信ページ"""
    player = supabase_client.get_player(discord_id)
    if not player:
        return RedirectResponse(url="/dashboard")

    return templates.TemplateResponse("dm_send.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "receiver_id": receiver_id or ""
    })


@router.post("/dm/send")
async def send_dm(
    receiver_id: str = Form(...),
    message: str = Form(...),
    discord_id: str = Depends(get_current_user)
):
    """DMを送信"""
    try:
        result = supabase_client.send_direct_message(discord_id, receiver_id, message)

        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=400)

        return RedirectResponse(url="/dm/sent", status_code=303)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/dm/read/{message_id}")
async def mark_read(message_id: int, discord_id: str = Depends(get_current_user)):
    """メッセージを既読にする"""
    try:
        result = supabase_client.mark_message_as_read(message_id, discord_id)

        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=403)

        return JSONResponse({"success": True})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/dm/delete/{message_id}")
async def delete_dm(message_id: int, discord_id: str = Depends(get_current_user)):
    """DMを削除"""
    try:
        result = supabase_client.delete_message_for_user(message_id, discord_id)

        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=403)

        return RedirectResponse(url="/dm/inbox", status_code=303)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)