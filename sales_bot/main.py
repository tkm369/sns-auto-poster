"""
main.py - 営業ボット メインオーケストレーター

使い方:
    python main.py twitter          # Twitter DM営業
    python main.py instagram        # Instagram DM営業
    python main.py email            # メール営業
    python main.py crowdworks       # CrowdWorks 自動応募
    python main.py lancers          # Lancers 自動応募
    python main.py all              # 全プラットフォーム
    python main.py status           # 送信済みリード確認
"""
import sys
import time
import random
import os
from playwright.sync_api import sync_playwright

import lead_db
import ai_writer
from prospector import scrape_twitter, scrape_instagram
from twitter_dm import send_twitter_dm
from instagram_dm import send_instagram_dm
from email_sender import send_email
from crowdworks import scrape_crowdworks, apply_crowdworks
from lancers import scrape_lancers, apply_lancers
from config import (
    TWITTER_PROFILE_DIR, INSTAGRAM_PROFILE_DIR,
    CROWDWORKS_PROFILE_DIR, LANCERS_PROFILE_DIR,
    TWITTER_SEARCH_KEYWORDS, INSTAGRAM_HASHTAGS,
    CROWDSOURCING_KEYWORDS, CS_BUDGET_MIN, MY_DESIRED_PRICE,
    TARGET_FOLLOWER_MIN, TARGET_FOLLOWER_MAX,
    MAX_DM_PER_DAY_TWITTER, MAX_DM_PER_DAY_INSTAGRAM, MAX_EMAIL_PER_DAY,
    MAX_APPLY_PER_DAY_CROWDWORKS, MAX_APPLY_PER_DAY_LANCERS,
    DM_INTERVAL_MIN, DM_INTERVAL_MAX,
    ANTHROPIC_API_KEY,
)


def _check_config():
    if not ANTHROPIC_API_KEY:
        print("[ERROR] ANTHROPIC_API_KEY が設定されていません。")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)


def run_twitter():
    _check_config()
    sent_today = lead_db.count_sent_today("twitter")
    remaining  = MAX_DM_PER_DAY_TWITTER - sent_today
    if remaining <= 0:
        print(f"[Twitter] 本日の上限 ({MAX_DM_PER_DAY_TWITTER}件) に達しました。")
        return

    print(f"[Twitter] 営業開始 (本日残り {remaining} 件)")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=TWITTER_PROFILE_DIR,
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.new_page() if not context.pages else context.pages[0]

        # ログイン確認
        page.goto("https://twitter.com/home", timeout=20000)
        page.wait_for_load_state("networkidle")
        if "login" in page.url:
            print("[ERROR] Twitterにログインされていません。先に python setup_login.py twitter を実行してください。")
            context.close()
            return

        # 見込み客リストアップ
        print("[Twitter] 見込み客を検索中...")
        leads = scrape_twitter(
            page,
            keywords=TWITTER_SEARCH_KEYWORDS,
            follower_min=TARGET_FOLLOWER_MIN,
            follower_max=TARGET_FOLLOWER_MAX,
            limit=remaining * 2,  # 余分に取っておく
        )
        print(f"[Twitter] {len(leads)} 件の候補を発見")

        sent = 0
        for lead in leads:
            if sent >= remaining:
                break
            if lead_db.already_contacted("twitter", lead.account_id):
                continue

            # メッセージ生成
            print(f"  → @{lead.username} ({lead.follower_count:,} followers, {lead.content_type})")
            message = ai_writer.generate_dm(
                platform="twitter",
                username=lead.username,
                display_name=lead.display_name,
                bio=lead.bio,
                follower_count=lead.follower_count,
                content_type=lead.content_type,
            )

            # 送信
            ok = send_twitter_dm(page, lead.username, message)
            if ok:
                lead_db.mark_sent("twitter", lead.account_id, lead.username, message)
                sent += 1
                wait = random.randint(DM_INTERVAL_MIN, DM_INTERVAL_MAX)
                print(f"  ({sent}/{remaining}) 次の送信まで {wait}秒 待機...")
                time.sleep(wait)

        context.close()

    print(f"[Twitter] 完了: {sent} 件送信")


def run_instagram():
    _check_config()
    sent_today = lead_db.count_sent_today("instagram")
    remaining  = MAX_DM_PER_DAY_INSTAGRAM - sent_today
    if remaining <= 0:
        print(f"[Instagram] 本日の上限 ({MAX_DM_PER_DAY_INSTAGRAM}件) に達しました。")
        return

    print(f"[Instagram] 営業開始 (本日残り {remaining} 件)")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=INSTAGRAM_PROFILE_DIR,
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.new_page() if not context.pages else context.pages[0]

        page.goto("https://www.instagram.com/", timeout=20000)
        page.wait_for_load_state("networkidle")
        if "accounts/login" in page.url:
            print("[ERROR] Instagramにログインされていません。先に python setup_login.py instagram を実行してください。")
            context.close()
            return

        print("[Instagram] 見込み客を検索中...")
        leads = scrape_instagram(
            page,
            hashtags=INSTAGRAM_HASHTAGS,
            follower_min=TARGET_FOLLOWER_MIN,
            follower_max=TARGET_FOLLOWER_MAX,
            limit=remaining * 2,
        )
        print(f"[Instagram] {len(leads)} 件の候補を発見")

        sent = 0
        for lead in leads:
            if sent >= remaining:
                break
            if lead_db.already_contacted("instagram", lead.account_id):
                continue

            print(f"  → @{lead.username} ({lead.follower_count:,} followers, {lead.content_type})")
            message = ai_writer.generate_dm(
                platform="instagram",
                username=lead.username,
                display_name=lead.display_name,
                bio=lead.bio,
                follower_count=lead.follower_count,
                content_type=lead.content_type,
            )

            ok = send_instagram_dm(page, lead.username, message)
            if ok:
                lead_db.mark_sent("instagram", lead.account_id, lead.username, message)
                sent += 1
                wait = random.randint(DM_INTERVAL_MIN, DM_INTERVAL_MAX)
                print(f"  ({sent}/{remaining}) 次の送信まで {wait}秒 待機...")
                time.sleep(wait)

        context.close()

    print(f"[Instagram] 完了: {sent} 件送信")


def run_email():
    """
    leads.json に保存されたリードのうち、emailが取れているものにメールを送信。
    DMで連絡済みのアカウントのメールアドレスは除外。
    """
    _check_config()
    sent_today = lead_db.count_sent_today("email")
    remaining  = MAX_EMAIL_PER_DAY - sent_today
    if remaining <= 0:
        print(f"[Email] 本日の上限 ({MAX_EMAIL_PER_DAY}件) に達しました。")
        return

    print(f"[Email] 営業開始 (本日残り {remaining} 件)")

    # leads.jsonからemailが取れているリードを収集
    all_leads = lead_db.all_leads()
    candidates = [
        l for l in all_leads
        if l.get("email") and not lead_db.already_contacted("email", l["account_id"])
    ]

    sent = 0
    for lead_data in candidates:
        if sent >= remaining:
            break

        print(f"  → {lead_data['email']} (@{lead_data['username']})")
        subject, body = ai_writer.generate_email(
            username=lead_data["username"],
            display_name=lead_data.get("display_name", ""),
            bio=lead_data.get("bio", ""),
            follower_count=lead_data.get("follower_count", 0),
            content_type=lead_data.get("content_type", "general"),
        )

        ok = send_email(lead_data["email"], subject, body)
        if ok:
            lead_db.mark_sent("email", lead_data["account_id"], lead_data["username"], body)
            sent += 1
            wait = random.randint(30, 90)
            print(f"  ({sent}/{remaining}) 次の送信まで {wait}秒 待機...")
            time.sleep(wait)

    print(f"[Email] 完了: {sent} 件送信")


def _run_crowdsourcing(platform: str, profile_dir: str, scrape_fn, apply_fn, max_per_day: int):
    _check_config()
    applied_today = lead_db.count_applied_today(platform)
    remaining     = max_per_day - applied_today
    if remaining <= 0:
        print(f"[{platform}] 本日の上限 ({max_per_day}件) に達しました。")
        return

    platform_label = {"crowdworks": "クラウドワークス", "lancers": "ランサーズ"}.get(platform, platform)
    print(f"[{platform_label}] 応募開始 (本日残り {remaining} 件)")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.new_page() if not context.pages else context.pages[0]

        # ログイン確認
        login_url = {
            "crowdworks": "https://crowdworks.jp/login",
            "lancers":    "https://www.lancers.jp/login",
        }[platform]
        home_url = {
            "crowdworks": "https://crowdworks.jp/",
            "lancers":    "https://www.lancers.jp/",
        }[platform]

        page.goto(home_url, timeout=20000)
        page.wait_for_load_state("networkidle")
        if "login" in page.url or "signin" in page.url:
            print(f"[ERROR] {platform_label} にログインされていません。")
            print(f"  先に python setup_login.py {platform} を実行してください。")
            context.close()
            return

        print(f"[{platform_label}] 案件を検索中...")
        jobs = scrape_fn(
            page,
            keywords=CROWDSOURCING_KEYWORDS,
            budget_min=CS_BUDGET_MIN,
            limit=remaining * 3,
        )
        print(f"[{platform_label}] {len(jobs)} 件の案件を発見")

        applied = 0
        for job in jobs:
            if applied >= remaining:
                break
            if lead_db.already_applied(platform, job.job_id):
                continue

            print(f"  → 【{job.title[:40]}】 {job.budget_text}")
            proposal = ai_writer.generate_proposal(
                platform=platform,
                job_title=job.title,
                job_description=job.description,
                budget_text=job.budget_text,
                job_type=job.job_type,
            )

            ok = apply_fn(page, job, proposal, price=MY_DESIRED_PRICE)
            if ok:
                lead_db.mark_applied(platform, job.job_id, job.title, proposal)
                applied += 1
                wait = random.randint(DM_INTERVAL_MIN, DM_INTERVAL_MAX)
                print(f"  ({applied}/{remaining}) 次の応募まで {wait}秒 待機...")
                time.sleep(wait)

        context.close()

    print(f"[{platform_label}] 完了: {applied} 件応募")


def run_crowdworks():
    _run_crowdsourcing(
        platform="crowdworks",
        profile_dir=CROWDWORKS_PROFILE_DIR,
        scrape_fn=scrape_crowdworks,
        apply_fn=apply_crowdworks,
        max_per_day=MAX_APPLY_PER_DAY_CROWDWORKS,
    )


def run_lancers():
    _run_crowdsourcing(
        platform="lancers",
        profile_dir=LANCERS_PROFILE_DIR,
        scrape_fn=scrape_lancers,
        apply_fn=apply_lancers,
        max_per_day=MAX_APPLY_PER_DAY_LANCERS,
    )


def show_status():
    leads = lead_db.all_leads()
    if not leads:
        print("まだリードがありません。")
        return

    by_status: dict[str, list] = {}
    for l in leads:
        s = l["status"]
        by_status.setdefault(s, []).append(l)

    print(f"\n{'='*40}")
    print(f"  リード管理ダッシュボード  (合計 {len(leads)} 件)")
    print(f"{'='*40}")
    for status, items in by_status.items():
        print(f"  {status:10s} : {len(items)} 件")

    print()
    by_platform: dict[str, int] = {}
    for l in leads:
        by_platform[l["platform"]] = by_platform.get(l["platform"], 0) + 1
    for plat, cnt in by_platform.items():
        print(f"  {plat:12s} : {cnt} 件")
    print()


COMMANDS = {
    "twitter":    run_twitter,
    "instagram":  run_instagram,
    "email":      run_email,
    "crowdworks": run_crowdworks,
    "lancers":    run_lancers,
    "status":     show_status,
}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "all":
        run_crowdworks()
        run_lancers()
        run_twitter()
        run_instagram()
        run_email()
    elif cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print("使い方:")
        print("  python main.py twitter     # Twitter DM営業")
        print("  python main.py instagram   # Instagram DM営業")
        print("  python main.py email       # メール営業")
        print("  python main.py crowdworks  # CrowdWorks 自動応募")
        print("  python main.py lancers     # Lancers 自動応募")
        print("  python main.py all         # 全プラットフォーム")
        print("  python main.py status      # リード確認")


if __name__ == "__main__":
    main()
