# supabase_client.py (web側)
from supabase import create_client
import os

def get_supabase_client():
    """Supabaseクライアントを取得（遅延初期化）"""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URLとSUPABASE_KEYの環境変数を設定してください")
    
    return create_client(url, key)

# グローバルクライアントを初期化
supabase = get_supabase_client()

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

# ==============================
# トレード関連機能(改修版)
# ==============================

def create_trade_request(sender_id, receiver_id, item_name, item_type="item"):
    """トレードリクエストを作成(保留機能付き)"""
    try:
        from datetime import datetime
        
        # 1. 送信者がアイテムを持っているか確認
        sender_player = get_player(sender_id)
        if not sender_player:
            return None
        
        inventory = sender_player.get("inventory", [])
        if item_name not in inventory:
            print(f"Item '{item_name}' not in sender's inventory")
            return None
        
        # 2. アイテムが既に保留中でないか確認
        if is_item_held(sender_id, item_name):
            print(f"Item '{item_name}' is already held in another trade")
            return None
        
        # 3. トレードを作成
        trade_data = {
            "sender_id": str(sender_id),
            "receiver_id": str(receiver_id),
            "item_name": item_name,
            "item_type": item_type,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("trades").insert(trade_data).execute()
        
        if response.data:
            trade_id = response.data[0]["id"]
            
            # 4. アイテムを保留状態にする
            if create_trade_hold(trade_id, sender_id, item_name):
                print(f"✅ Trade {trade_id} created and item held")
                return response.data[0]
            else:
                # 保留に失敗したらトレードを削除
                supabase.table("trades").delete().eq("id", trade_id).execute()
                return None
        
        return None
    except Exception as e:
        print(f"Error creating trade: {e}")
        import traceback
        traceback.print_exc()
        return None

def approve_trade(trade_id):
    """トレードを承認(保留解除付き)"""
    try:
        # 1. トレード情報を取得
        trade = supabase.table("trades").select("*").eq("id", trade_id).execute()
        if not trade.data:
            return False
        
        trade_data = trade.data[0]
        
        # トレードが既に処理済みでないか確認
        if trade_data.get("status") != "pending":
            print(f"Trade {trade_id} is not pending")
            return False
        
        sender_id = trade_data["sender_id"]
        receiver_id = trade_data["receiver_id"]
        item_name = trade_data["item_name"]
        
        # 2. 送信者と受信者の検証
        sender_player = get_player(sender_id)
        receiver_player = get_player(receiver_id)
        
        if not sender_player or not receiver_player:
            update_trade_status(trade_id, "failed")
            release_trade_hold(trade_id)
            return False
        
        # 3. アイテムが保留されているか確認
        if not is_item_held(sender_id, item_name):
            print(f"Item '{item_name}' is not held")
            update_trade_status(trade_id, "failed")
            return False
        
        # 4. アイテム移動
        sender_inventory = sender_player.get("inventory", [])
        
        # アイテムが実際にインベントリにあるか確認
        if item_name not in sender_inventory:
            update_trade_status(trade_id, "failed")
            release_trade_hold(trade_id)
            return False
        
        # 送信者から削除
        sender_inventory.remove(item_name)
        update_player(sender_id, inventory=sender_inventory)
        
        # 受信者に追加
        receiver_inventory = receiver_player.get("inventory", [])
        receiver_inventory.append(item_name)
        update_player(receiver_id, inventory=receiver_inventory)
        
        # 5. トレード完了処理
        update_trade_status(trade_id, "approved")
        release_trade_hold(trade_id)  # 保留解除
        
        print(f"✅ Trade {trade_id} approved and hold released")
        return True
        
    except Exception as e:
        print(f"❌ Error approving trade: {e}")
        import traceback
        traceback.print_exc()
        return False

def reject_trade(trade_id):
    """トレードを拒否(保留解除)"""
    try:
        # トレードステータスを更新
        result = update_trade_status(trade_id, "rejected")
        
        # 保留を解除(アイテムが送信者に戻る)
        if result:
            release_trade_hold(trade_id)
            print(f"✅ Trade {trade_id} rejected and hold released")
        
        return result
    except Exception as e:
        print(f"Error rejecting trade: {e}")
        return False

def get_available_inventory(user_id):
    """利用可能なインベントリ(保留中を除く)を取得"""
    player = get_player(user_id)
    if not player:
        return []
    
    inventory = player.get("inventory", [])
    held_items = get_held_items(user_id)
    
    # 保留中のアイテムを除外
    available = []
    for item in inventory:
        if item not in held_items or inventory.count(item) > held_items.count(item):
            available.append(item)
    
    return available
    
    
def is_player_bot_banned(user_id):
    """プレイヤーがBOT利用禁止かチェック"""
    player = get_player(user_id)
    if player:
        return player.get("bot_banned", False)
    return False
def is_player_web_banned(user_id):
    """プレイヤーがWeb利用禁止かチェック"""
    player = get_player(user_id)
    if player:
        return player.get("web_banned", False)
    return False
def set_bot_ban(user_id, banned=True):
    """BOT利用禁止を設定/解除"""
    try:
        update_player(user_id, bot_banned=banned)
        return True
    except Exception as e:
        print(f"Error setting bot ban: {e}")
        return False
def set_web_ban(user_id, banned=True):
    """Web利用禁止を設定/解除"""
    try:
        update_player(user_id, web_banned=banned)
        return True
    except Exception as e:
        print(f"Error setting web ban: {e}")
        return False
def get_ban_status(user_id):
    """BAN状態を取得"""
    player = get_player(user_id)
    if player:
        return {
            "bot_banned": player.get("bot_banned", False),
            "web_banned": player.get("web_banned", False)
        }
    return {"bot_banned": False, "web_banned": False}
    

def create_trade_proposal(sender_id, receiver_id, item_names):
    """トレード提案を作成 (複数アイテム対応)"""
    try:
        from datetime import datetime
        
        # 送信者がアイテムを持っているか確認
        sender_player = get_player(sender_id)
        if not sender_player:
            return None
        
        inventory = sender_player.get("inventory", [])
        for item in item_names:
            if item not in inventory:
                print(f"Item '{item}' not in sender's inventory")
                return None
        
        # アイテムが既に保留中でないか確認
        for item in item_names:
            if is_item_held(sender_id, item):
                print(f"Item '{item}' is already held")
                return None
        
        # トレード提案作成
        trade_data = {
            "sender_id": str(sender_id),
            "receiver_id": str(receiver_id),
            "sender_items": item_names,
            "receiver_items": [],
            "receiver_responded": False,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("trades").insert(trade_data).execute()
        
        if response.data:
            trade_id = response.data[0]["id"]
            
            # 各アイテムを保留状態にする
            for item in item_names:
                create_trade_hold(trade_id, sender_id, item)
            
            print(f"✅ Trade proposal {trade_id} created")
            return response.data[0]
        
        return None
    except Exception as e:
        print(f"Error creating trade proposal: {e}")
        import traceback
        traceback.print_exc()
        return None

def set_receiver_items(trade_id, item_names):
    """受信者がアイテムを提示 (ステータスをwaiting_senderに変更)"""
    try:
        from datetime import datetime
        
        # トレード情報取得
        trade = supabase.table("trades").select("*").eq("id", trade_id).execute()
        if not trade.data:
            return False
        
        trade_data = trade.data[0]
        receiver_id = trade_data["receiver_id"]
        
        # 受信者がアイテムを持っているか確認
        receiver_player = get_player(receiver_id)
        if not receiver_player:
            return False
        
        inventory = receiver_player.get("inventory", [])
        for item in item_names:
            if item not in inventory:
                print(f"Item '{item}' not in receiver's inventory")
                return False
        
        # アイテムが既に保留中でないか確認
        for item in item_names:
            if is_item_held(receiver_id, item):
                print(f"Item '{item}' is already held")
                return False
        
        # トレード更新
        update_data = {
            "receiver_items": item_names,
            "receiver_responded": True,
            "status": "waiting_sender",
            "updated_at": datetime.utcnow().isoformat()
        }
        supabase.table("trades").update(update_data).eq("id", trade_id).execute()
        
        # 受信者のアイテムを保留
        for item in item_names:
            create_trade_hold(trade_id, receiver_id, item)
        
        print(f"✅ Receiver items set for trade {trade_id}")
        return True
        
    except Exception as e:
        print(f"Error setting receiver items: {e}")
        import traceback
        traceback.print_exc()
        return False

def complete_trade(trade_id):
    """トレードを完了 (アイテム交換実行)"""
    try:
        from datetime import datetime
        
        # トレード情報取得
        trade = supabase.table("trades").select("*").eq("id", trade_id).execute()
        if not trade.data:
            return False
        
        trade_data = trade.data[0]
        sender_id = trade_data["sender_id"]
        receiver_id = trade_data["receiver_id"]
        sender_items = trade_data.get("sender_items", [])
        receiver_items = trade_data.get("receiver_items", [])
        
        # 送信者のプレイヤーデータ取得
        sender_player = get_player(sender_id)
        receiver_player = get_player(receiver_id)
        
        if not sender_player or not receiver_player:
            return False
        
        # 送信者のインベントリ操作
        sender_inventory = sender_player.get("inventory", [])
        for item in sender_items:
            if item in sender_inventory:
                sender_inventory.remove(item)
        
        # 受信者のアイテムを送信者に追加
        for item in receiver_items:
            sender_inventory.append(item)
        
        update_player(sender_id, inventory=sender_inventory)
        
        # 受信者のインベントリ操作
        receiver_inventory = receiver_player.get("inventory", [])
        for item in receiver_items:
            if item in receiver_inventory:
                receiver_inventory.remove(item)
        
        # 送信者のアイテムを受信者に追加
        for item in sender_items:
            receiver_inventory.append(item)
        
        update_player(receiver_id, inventory=receiver_inventory)
        
        # トレードステータス更新
        update_data = {
            "status": "completed",
            "updated_at": datetime.utcnow().isoformat()
        }
        supabase.table("trades").update(update_data).eq("id", trade_id).execute()
        
        # 保留解除
        release_trade_hold(trade_id)
        
        print(f"✅ Trade {trade_id} completed successfully")
        return True
        
    except Exception as e:
        print(f"Error completing trade: {e}")
        import traceback
        traceback.print_exc()
        return False

def reject_trade(trade_id):
    """トレードを拒否 (保留解除)"""
    try:
        from datetime import datetime
        
        # ステータス更新
        update_data = {
            "status": "rejected",
            "updated_at": datetime.utcnow().isoformat()
        }
        supabase.table("trades").update(update_data).eq("id", trade_id).execute()
        
        # 保留解除
        release_trade_hold(trade_id)
        
        print(f"✅ Trade {trade_id} rejected")
        return True
        
    except Exception as e:
        print(f"Error rejecting trade: {e}")
        return False

def get_my_trades(user_id):
    """自分に関連する全トレードを状態別に取得"""
    try:
        # 受信したトレード (pending)
        received_pending = supabase.table("trades").select("*").eq(
            "receiver_id", str(user_id)
        ).eq("status", "pending").order("created_at", desc=True).execute()
        
        # 送信したトレード (相手待ち)
        sent_waiting = supabase.table("trades").select("*").eq(
            "sender_id", str(user_id)
        ).eq("status", "pending").order("created_at", desc=True).execute()
        
        # 送信したトレード (自分の最終確認待ち)
        sent_final = supabase.table("trades").select("*").eq(
            "sender_id", str(user_id)
        ).eq("status", "waiting_sender").order("created_at", desc=True).execute()
        
        return {
            "received_pending": received_pending.data if received_pending.data else [],
            "sent_waiting_receiver": sent_waiting.data if sent_waiting.data else [],
            "sent_waiting_sender": sent_final.data if sent_final.data else []
        }
        
    except Exception as e:
        print(f"Error getting my trades: {e}")
        return {
            "received_pending": [],
            "sent_waiting_receiver": [],
            "sent_waiting_sender": []
        }