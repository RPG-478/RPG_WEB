# supabase_client.py (web側)
from supabase import create_client
import os

_supabase_client = None

def get_supabase_client():
    """Supabaseクライアントを取得（遅延初期化）"""
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        # 開発環境で環境変数未設定の場合、Noneを返す
        return None

    _supabase_client = create_client(url, key)
    return _supabase_client

# Create a module-level wrapper that safely handles None
class SupabaseClientWrapper:
    def __getattr__(self, name):
        client = get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase未設定: SUPABASE_URLとSUPABASE_KEYを環境変数に設定してください")
        return getattr(client, name)

supabase = SupabaseClientWrapper()

def get_player(user_id):
    """プレイヤーデータを取得"""
    res = supabase.table("players").select("*").eq("user_id", str(user_id)).execute()
    return res.data[0] if res.data else None

def create_player(user_id: int):
    """新規プレイヤーを作成（デフォルト値はテーブル定義に従う）"""
    supabase.table("players").insert({
        "user_id": str(user_id)
    }).execute()

def update_player(user_id, **kwargs):
    """プレイヤーデータを更新"""
    supabase.table("players").update(kwargs).eq("user_id", str(user_id)).execute()

def delete_player(user_id):
    """プレイヤーデータを削除"""
    supabase.table("players").delete().eq("user_id", str(user_id)).execute()

def add_item_to_inventory(user_id, item_name):
    """インベントリにアイテムを追加"""
    player = get_player(user_id)
    if player:
        inventory = player.get("inventory", [])
        inventory.append(item_name)
        update_player(user_id, inventory=inventory)

def remove_item_from_inventory(user_id, item_name):
    """インベントリからアイテムを削除"""
    player = get_player(user_id)
    if player:
        inventory = player.get("inventory", [])
        if item_name in inventory:
            inventory.remove(item_name)
            update_player(user_id, inventory=inventory)

def add_gold(user_id, amount):
    """ゴールドを追加"""
    player = get_player(user_id)
    if player:
        current_gold = player.get("gold", 0)
        update_player(user_id, gold=current_gold + amount)

def get_equipped_items(user_id):
    """装備中のアイテムを取得"""
    player = get_player(user_id)
    if player:
        return {
            "weapon": player.get("equipped_weapon"),
            "armor": player.get("equipped_armor")
        }
    return {"weapon": None, "armor": None}

def equip_weapon(user_id, weapon_name):
    """武器を装備"""
    update_player(user_id, equipped_weapon=weapon_name)

def equip_armor(user_id, armor_name):
    """防具を装備"""
    update_player(user_id, equipped_armor=armor_name)

# ==============================
# トレード関連機能
# ==============================

def create_trade_request(sender_id, receiver_id, item_name, item_type="item"):
    """トレードリクエストを作成"""
    try:
        from datetime import datetime
        trade_data = {
            "sender_id": str(sender_id),
            "receiver_id": str(receiver_id),
            "item_name": item_name,
            "item_type": item_type,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("trades").insert(trade_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating trade: {e}")
        return None

def get_trade_history(user_id):
    """トレード履歴を取得"""
    try:
        response = supabase.table("trades").select("*").or_(
            f"sender_id.eq.{user_id},receiver_id.eq.{user_id}"
        ).order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting trade history: {e}")
        return []

def get_pending_trades(user_id):
    """保留中のトレードを取得"""
    try:
        response = supabase.table("trades").select("*").eq(
            "receiver_id", str(user_id)
        ).eq("status", "pending").order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting pending trades: {e}")
        return []

def update_trade_status(trade_id, status):
    """トレードステータスを更新"""
    try:
        from datetime import datetime
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        supabase.table("trades").update(update_data).eq("id", trade_id).execute()
        return True
    except Exception as e:
        print(f"Error updating trade status: {e}")
        return False

def approve_trade(trade_id):
    """トレードを承認"""
    try:
        # トレード情報を取得
        trade = supabase.table("trades").select("*").eq("id", trade_id).execute()
        if not trade.data:
            print(f"Trade {trade_id} not found")
            return False

        trade_data = trade.data[0]
        sender_id = trade_data["sender_id"]
        receiver_id = trade_data["receiver_id"]
        item_name = trade_data["item_name"]

        # 送信者のプレイヤーデータを取得
        sender_player = get_player(sender_id)
        if not sender_player:
            print(f"Sender {sender_id} not found")
            return False

        # 送信者のインベントリを確認
        inventory = sender_player.get("inventory", [])
        if item_name not in inventory:
            print(f"Item '{item_name}' not in sender's inventory")
            return False

        # アイテムを削除
        inventory.remove(item_name)
        update_player(sender_id, inventory=inventory)

        # 削除後のインベントリを再確認(デバッグ用)
        sender_after = get_player(sender_id)
        print(f"Sender inventory after removal: {sender_after.get('inventory', [])}")

        # 受信者にアイテムを追加
        receiver_player = get_player(receiver_id)
        if receiver_player:
            receiver_inventory = receiver_player.get("inventory", [])
            receiver_inventory.append(item_name)
            update_player(receiver_id, inventory=receiver_inventory)
            print(f"Receiver inventory after addition: {receiver_inventory}")
        else:
            # 受信者が存在しない場合、送信者にアイテムを戻す
            inventory.append(item_name)
            update_player(sender_id, inventory=inventory)
            print(f"Receiver not found, item returned to sender")
            return False

        # トレードステータスを更新
        update_trade_status(trade_id, "approved")
        return True

    except Exception as e:
        print(f"Error approving trade: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==============================
# 倉庫システム
# ==============================

def add_to_storage(user_id, item_name, item_type):
    """倉庫にアイテムを追加"""
    try:
        supabase.table("storage").insert({
            "user_id": str(user_id),
            "item_name": item_name,
            "item_type": item_type,
            "is_taken": False
        }).execute()
        return True
    except Exception as e:
        print(f"Error adding to storage: {e}")
        return False

def get_storage_items(user_id, include_taken=False):
    """倉庫のアイテムリストを取得"""
    try:
        query = supabase.table("storage").select("*").eq("user_id", str(user_id))

        if not include_taken:
            query = query.eq("is_taken", False)

        res = query.order("stored_at", desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"Error getting storage items: {e}")
        return []

def get_storage_item_by_id(storage_id):
    """IDで倉庫アイテムを取得"""
    try:
        res = supabase.table("storage").select("*").eq("id", storage_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Error getting storage item: {e}")
        return None

def take_from_storage(user_id, storage_id):
    """倉庫からアイテムを取り出す"""
    try:
        supabase.table("storage").update({
            "is_taken": True
        }).eq("id", storage_id).eq("user_id", str(user_id)).execute()
        return True
    except Exception as e:
        print(f"Error taking from storage: {e}")
        return False

# ==============================
# トレード保留システム
# ==============================

def create_trade_hold(trade_id, user_id, item_name):
    """トレードアイテムを保留状態にする"""
    try:
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + timedelta(hours=24)

        supabase.table("trade_holds").insert({
            "trade_id": trade_id,
            "user_id": str(user_id),
            "item_name": item_name,
            "expires_at": expires_at.isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Error creating trade hold: {e}")
        return False

def release_trade_hold(trade_id):
    """トレード保留を解除"""
    try:
        supabase.table("trade_holds").delete().eq("trade_id", trade_id).execute()
        return True
    except Exception as e:
        print(f"Error releasing trade hold: {e}")
        return False

def get_held_items(user_id):
    """ユーザーの保留中アイテムリストを取得"""
    try:
        res = supabase.table("trade_holds").select("*").eq("user_id", str(user_id)).execute()
        return [item["item_name"] for item in res.data] if res.data else []
    except Exception as e:
        print(f"Error getting held items: {e}")
        return []

def is_item_held(user_id, item_name):
    """アイテムが保留中かチェック"""
    try:
        res = supabase.table("trade_holds").select("*").eq(
            "user_id", str(user_id)
        ).eq("item_name", item_name).execute()
        return len(res.data) > 0 if res.data else False
    except Exception as e:
        print(f"Error checking item hold: {e}")
        return False

def cleanup_expired_holds():
    """期限切れの保留を自動解除"""
    try:
        from datetime import datetime
        now = datetime.utcnow().isoformat()

        # 期限切れの保留を取得
        expired = supabase.table("trade_holds").select("*").lt("expires_at", now).execute()

        if expired.data:
            for hold in expired.data:
                trade_id = hold["trade_id"]

                # トレードを期限切れに設定
                update_trade_status(trade_id, "expired")

                # 保留を解除
                release_trade_hold(trade_id)

                print(f"Trade {trade_id} expired and hold released")

        return True
    except Exception as e:
        print(f"Error cleaning up expired holds: {e}")
        return False

# Placeholder functions for other features (add implementation as needed)
def get_my_trades(user_id):
    """自分に関連するトレードを取得"""
    return {
        "received_pending": [],
        "sent_waiting_receiver": [],
        "sent_waiting_sender": []
    }

def get_available_inventory(user_id):
    """利用可能なインベントリを取得"""
    player = get_player(user_id)
    if player:
        return player.get("inventory", [])
    return []

def create_trade_proposal(sender_id, receiver_id, item_names):
    """トレード提案を作成"""
    return None

def reject_trade(trade_id):
    """トレードを拒否"""
    return update_trade_status(trade_id, "rejected")

def set_receiver_items(trade_id, item_names):
    """受信者のアイテムを設定"""
    return False

def complete_trade(trade_id):
    """トレードを完了"""
    return False

def get_received_messages(user_id):
    """受信したメッセージを取得"""
    return []

def get_sent_messages(user_id):
    """送信したメッセージを取得"""
    return []

def get_unread_count(user_id):
    """未読件数を取得"""
    return 0

def send_direct_message(sender_id, receiver_id, message):
    """DMを送信"""
    return {"error": "Not implemented"}

def mark_message_as_read(message_id, user_id):
    """メッセージを既読にする"""
    return {"error": "Not implemented"}

def delete_message_for_user(message_id, user_id):
    """DMを削除"""
    return {"error": "Not implemented"}

def get_active_trade_posts():
    """有効な投稿を取得"""
    return []

def get_my_trade_posts(user_id):
    """自分の投稿を取得"""
    return []

def create_trade_post(user_id, title, offering_items, wanting_items, message):
    """トレード募集を投稿"""
    return {"error": "Not implemented"}

def delete_trade_post(post_id, user_id):
    """投稿を削除"""
    return {"error": "Not implemented"}

def cleanup_expired_trade_posts():
    """期限切れのトレード投稿をクリーンアップ"""
    return True
