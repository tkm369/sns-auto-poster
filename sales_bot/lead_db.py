"""
lead_db.py - リード管理 (JSON)
送信済み・返信済み・成約をトラッキング
"""
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "leads.json"


def _load() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"leads": {}}


def _save(db: dict):
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def already_contacted(platform: str, account_id: str) -> bool:
    db = _load()
    key = f"{platform}:{account_id}"
    return key in db["leads"]


def mark_sent(platform: str, account_id: str, username: str, message: str):
    db = _load()
    key = f"{platform}:{account_id}"
    db["leads"][key] = {
        "platform": platform,
        "account_id": account_id,
        "username": username,
        "message_sent": message,
        "status": "sent",
        "sent_at": datetime.now().isoformat(),
        "replied_at": None,
        "notes": "",
    }
    _save(db)


def mark_replied(platform: str, account_id: str):
    db = _load()
    key = f"{platform}:{account_id}"
    if key in db["leads"]:
        db["leads"][key]["status"] = "replied"
        db["leads"][key]["replied_at"] = datetime.now().isoformat()
        _save(db)


def count_sent_today(platform: str) -> int:
    db = _load()
    today = datetime.now().date().isoformat()
    return sum(
        1 for v in db["leads"].values()
        if v["platform"] == platform
        and v.get("sent_at", "")[:10] == today
    )


def all_leads() -> list:
    return list(_load()["leads"].values())


# ─── クラウドソーシング案件応募トラッキング ────────────────

def already_applied(platform: str, job_id: str) -> bool:
    db = _load()
    key = f"job:{platform}:{job_id}"
    return key in db["leads"]


def mark_applied(platform: str, job_id: str, job_title: str, proposal: str):
    db = _load()
    key = f"job:{platform}:{job_id}"
    db["leads"][key] = {
        "platform": platform,
        "account_id": job_id,
        "username": job_title,
        "message_sent": proposal,
        "status": "applied",
        "sent_at": datetime.now().isoformat(),
        "replied_at": None,
        "notes": "",
        "record_type": "job",
    }
    _save(db)


def count_applied_today(platform: str) -> int:
    db = _load()
    today = datetime.now().date().isoformat()
    return sum(
        1 for v in db["leads"].values()
        if v.get("record_type") == "job"
        and v["platform"] == platform
        and v.get("sent_at", "")[:10] == today
    )
