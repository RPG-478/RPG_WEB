from datetime import datetime, timedelta
import supabase_client

def check_account_lock(discord_id: str) -> dict:
    """アカウントロック状態をチェック (5分間に3回失敗 → 10分ロック)"""
    try:
        # 5分以内の失敗回数を取得
        five_min_ago = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

        attempts = supabase_client.supabase.table("login_attempts").select("*").eq(
            "discord_id", discord_id
        ).eq("success", False).gte("created_at", five_min_ago).execute()

        failed_count = len(attempts.data) if attempts.data else 0

        if failed_count >= 3:
            # 最後の失敗から10分以内か確認
            last_attempt = attempts.data[-1]["created_at"]
            last_time = datetime.fromisoformat(last_attempt.replace('Z', '+00:00'))
            unlock_time = last_time + timedelta(minutes=10)

            if datetime.utcnow() < unlock_time.replace(tzinfo=None):
                return {
                    "locked": True,
                    "unlock_at": unlock_time.isoformat(),
                    "reason": "5分間に3回ログインに失敗しました"
                }

        return {"locked": False}

    except Exception as e:
        print(f"Error checking account lock: {e}")
        return {"locked": False}

def check_safe_mode_trigger() -> bool:
    """SAFE_MODE発動条件チェック (5分以内に5回以上 + 異なるIP 2個以上)"""
    try:
        five_min_ago = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

        attempts = supabase_client.supabase.table("login_attempts").select("*").eq(
            "success", False
        ).gte("created_at", five_min_ago).execute()

        if not attempts.data or len(attempts.data) < 5:
            return False

        # 異なるIPアドレスの数をカウント
        unique_ips = set(attempt["ip_address"] for attempt in attempts.data)

        if len(attempts.data) >= 5 and len(unique_ips) >= 2:
            return True

        return False

    except Exception as e:
        print(f"Error checking safe mode trigger: {e}")
        return False

def activate_safe_mode(reason: str):
    """SAFE_MODEを発動"""
    try:
        from datetime import datetime
        supabase_client.supabase.table("system_status").update({
            "is_safe_mode": True,
            "locked_at": datetime.utcnow().isoformat(),
            "locked_reason": reason
        }).eq("id", 1).execute()

        print(f"🚨 SAFE_MODE発動: {reason}")
        return True
    except Exception as e:
        print(f"Error activating safe mode: {e}")
        return False

def is_safe_mode_active() -> bool:
    """SAFE_MODE状態を確認"""
    try:
        status = supabase_client.supabase.table("system_status").select("*").eq("id", 1).single().execute()
        return status.data.get("is_safe_mode", False) if status.data else False
    except Exception as e:
        print(f"Error checking safe mode: {e}")
        return False

def record_login_attempt(discord_id: str, ip_address: str, success: bool):
    """ログイン試行を記録"""
    try:
        from datetime import datetime
        supabase_client.supabase.table("login_attempts").insert({
            "discord_id": discord_id,
            "ip_address": ip_address,
            "success": success,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error recording login attempt: {e}")

def get_client_ip(request) -> str:
    """クライアントのIPアドレスを取得"""
    # X-Forwarded-For ヘッダーから取得 (プロキシ経由の場合)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # X-Real-IP ヘッダーから取得
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # 直接接続の場合
    return request.client.host if request.client else "unknown"