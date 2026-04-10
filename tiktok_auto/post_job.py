"""
post_job.py - タスクスケジューラから呼ばれる1投稿スクリプト
"""
import sys, os, time, json, logging
from logging.handlers import RotatingFileHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOG_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiktok_auto.log")
QUEUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "queue.json")

# ログローテーション: 5MB × 3世代
rotating_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[rotating_handler, logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def cleanup_queue(keep_done: int = 200):
    """done/skipped が古い順に溢れたら削除。pending/failed は全件保持。"""
    if not os.path.exists(QUEUE_FILE):
        return
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    active   = [i for i in queue if i["status"] in ("pending", "failed")]
    finished = [i for i in queue if i["status"] not in ("pending", "failed")]

    if len(finished) > keep_done:
        # 古い順に捨てる（added_at昇順の末尾keep_done件だけ残す）
        finished = sorted(finished, key=lambda x: x.get("added_at", ""))[-keep_done:]
        removed = len(queue) - len(active) - len(finished)
        logger.info(f"queue.json クリーンアップ: {removed}件削除")

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(active + finished, f, ensure_ascii=False, indent=2)


# ----- メイン -----
from fetcher import fetch_and_enqueue
from scheduler import run_post_job

cleanup_queue()

logger.info("=== STEP1: fetch_and_enqueue 開始 ===")
t0 = time.time()
fetch_and_enqueue()
logger.info(f"=== STEP1完了: {time.time()-t0:.1f}秒 ===")

logger.info("=== STEP2: run_post_job 開始 ===")
t1 = time.time()
run_post_job()
logger.info(f"=== STEP2完了: {time.time()-t1:.1f}秒 ===")
