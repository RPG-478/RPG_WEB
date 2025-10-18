from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from utils.auth import get_current_user
import supabase_client

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/trade-board", response_class=HTMLResponse)
async def trade_board_page(request: Request, discord_id: str = Depends(get_current_user)):
    """トレード掲示板ページ"""
    player = supabase_client.get_player(discord_id)
    if not player:
        return RedirectResponse(url="/dashboard")

    # 有効な投稿を取得
    posts = supabase_client.get_active_trade_posts()

    # 自分の投稿を取得
    my_posts = supabase_client.get_my_trade_posts(discord_id)

    # 利用可能なインベントリ
    available_inventory = supabase_client.get_available_inventory(discord_id)

    return templates.TemplateResponse("trade_board.html", {
        "request": request,
        "discord_id": discord_id,
        "player": player,
        "posts": posts,
        "my_posts": my_posts,
        "available_inventory": available_inventory
    })


@router.post("/trade-board/post")
async def create_post(
    title: str = Form(...),
    offering_items: list = Form(...),
    wanting_items: str = Form(...),
    message: str = Form(default=""),
    discord_id: str = Depends(get_current_user)
):
    """トレード募集を投稿"""
    try:
        result = supabase_client.create_trade_post(
            discord_id, title, offering_items, wanting_items, message
        )

        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=400)

        return RedirectResponse(url="/trade-board", status_code=303)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/trade-board/delete/{post_id}")
async def delete_post(post_id: int, discord_id: str = Depends(get_current_user)):
    """投稿を削除"""
    try:
        result = supabase_client.delete_trade_post(post_id, discord_id)

        if "error" in result:
            return JSONResponse({"error": result["error"]}, status_code=403)

        return RedirectResponse(url="/trade-board", status_code=303)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)