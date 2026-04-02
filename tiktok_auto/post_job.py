"""
post_job.py - タスクスケジューラから呼ばれる1投稿スクリプト
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiktok_auto.log"),
            encoding="utf-8"
        ),
        logging.StreamHandler(),
    ]
)

from scheduler import run_post_job
run_post_job()
