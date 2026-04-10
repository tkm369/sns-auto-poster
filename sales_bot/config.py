import os

# === Anthropic (Claude) API ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# === Gmail (メール送信) ===
GMAIL_ADDRESS  = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")   # Googleアプリパスワード

# === プロファイル保存先 ===
TWITTER_PROFILE_DIR   = os.getenv("TWITTER_PROFILE_DIR",   r"C:\sales_bot_profiles\twitter")
INSTAGRAM_PROFILE_DIR = os.getenv("INSTAGRAM_PROFILE_DIR", r"C:\sales_bot_profiles\instagram")

# === 営業設定 ===
MY_NAME          = os.getenv("MY_NAME", "あなたの名前")
MY_SERVICE       = os.getenv("MY_SERVICE", "動画編集")
MY_PORTFOLIO_URL = os.getenv("MY_PORTFOLIO_URL", "")   # ポートフォリオURL (任意)
MY_CONTACT       = os.getenv("MY_CONTACT", "")         # 連絡先 (Twitter IDやメール)

# 1日の最大送信数 (各プラットフォーム)
MAX_DM_PER_DAY_TWITTER   = int(os.getenv("MAX_DM_PER_DAY_TWITTER", "20"))
MAX_DM_PER_DAY_INSTAGRAM = int(os.getenv("MAX_DM_PER_DAY_INSTAGRAM", "15"))
MAX_EMAIL_PER_DAY        = int(os.getenv("MAX_EMAIL_PER_DAY", "30"))

# DM間隔 (秒, min-max)
DM_INTERVAL_MIN = int(os.getenv("DM_INTERVAL_MIN", "60"))
DM_INTERVAL_MAX = int(os.getenv("DM_INTERVAL_MAX", "180"))

# ターゲット検索キーワード (スペース区切りで追加可)
TWITTER_SEARCH_KEYWORDS = os.getenv(
    "TWITTER_SEARCH_KEYWORDS",
    "YouTuber 動画編集 Vlog ゲーム実況 投資 ビジネス系YouTuber"
).split()

INSTAGRAM_HASHTAGS = os.getenv(
    "INSTAGRAM_HASHTAGS",
    "youtuber 動画編集 vlog ゲーム実況 ビジネス系youtuber"
).split()

# フォロワー数フィルター
TARGET_FOLLOWER_MIN = int(os.getenv("TARGET_FOLLOWER_MIN", "1000"))
TARGET_FOLLOWER_MAX = int(os.getenv("TARGET_FOLLOWER_MAX", "100000"))

# === クラウドソーシング設定 ===
CROWDWORKS_PROFILE_DIR = os.getenv("CROWDWORKS_PROFILE_DIR", r"C:\sales_bot_profiles\crowdworks")
LANCERS_PROFILE_DIR    = os.getenv("LANCERS_PROFILE_DIR",    r"C:\sales_bot_profiles\lancers")

# 検索キーワード (スペース区切り)
CROWDSOURCING_KEYWORDS = os.getenv(
    "CROWDSOURCING_KEYWORDS",
    "動画編集 動画制作 YouTube編集 ショート動画 Reels編集 TikTok編集"
).split()

# 最低予算フィルター (円, 0=フィルターなし)
CS_BUDGET_MIN = int(os.getenv("CS_BUDGET_MIN", "3000"))

# 1日の最大応募数 (各サービス)
MAX_APPLY_PER_DAY_CROWDWORKS = int(os.getenv("MAX_APPLY_PER_DAY_CROWDWORKS", "10"))
MAX_APPLY_PER_DAY_LANCERS    = int(os.getenv("MAX_APPLY_PER_DAY_LANCERS",    "10"))

# 応募時の希望単価 (0=入力しない)
MY_DESIRED_PRICE = int(os.getenv("MY_DESIRED_PRICE", "0"))
