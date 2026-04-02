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
AFFILIATE_LINK = os.getenv("AFFILIATE_LINK", "")  # 空のまま = アフィリなしモード
AFFILIATE_TEXT = "🔮 詳しい鑑定はこちら →"
