import os

# === Gemini API (無料) ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# === X (Twitter) API ===
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

# === Threads API ===
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")

# === アフィリエイト設定 ===
_raw_affiliate = os.getenv("AFFILIATE_LINK", "").strip()
# http(s)で始まる正規のURLでなければ無効とみなす
AFFILIATE_LINK = _raw_affiliate if _raw_affiliate.startswith("http") else ""
AFFILIATE_TEXT = "🔮 詳しい鑑定はこちら →"
