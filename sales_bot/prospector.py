"""
prospector.py - 見込み客を検索してリストアップ
Twitter/X と Instagram から Playwright でスクレイプ
"""
import re
import time
import random
from dataclasses import dataclass, field
from playwright.sync_api import Page


@dataclass
class Lead:
    platform: str
    account_id: str       # 一意ID (username など)
    username: str
    display_name: str
    bio: str
    follower_count: int
    email: str = ""
    content_type: str = "general"
    profile_url: str = ""


def _parse_follower_count(text: str) -> int:
    """'12.3K' '1.2M' '5000' などをintに変換"""
    text = text.replace(",", "").strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    if "M" in text.upper():
        return int(float(text.upper().replace("M", "")) * 1_000_000)
    if "K" in text.upper():
        return int(float(text.upper().replace("K", "")) * 1000)
    try:
        return int(text)
    except ValueError:
        return 0


def _guess_content_type(bio: str, username: str) -> str:
    text = (bio + " " + username).lower()
    if any(w in text for w in ["ゲーム", "game", "gaming", "fps", "apex", "valorant"]):
        return "gaming"
    if any(w in text for w in ["投資", "資産", "副業", "ビジネス", "起業", "稼ぐ"]):
        return "business"
    if any(w in text for w in ["vlog", "日常", "旅行", "travel"]):
        return "vlog"
    if any(w in text for w in ["メイク", "ファッション", "コスメ", "beauty"]):
        return "lifestyle"
    if any(w in text for w in ["料理", "グルメ", "food", "cooking"]):
        return "food"
    return "general"


def _extract_email_from_bio(bio: str) -> str:
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", bio)
    return match.group(0) if match else ""


# ─── Twitter ──────────────────────────────────────────────

def scrape_twitter(
    page: Page,
    keywords: list[str],
    follower_min: int,
    follower_max: int,
    limit: int = 50,
) -> list[Lead]:
    leads = []
    seen = set()

    for kw in keywords:
        if len(leads) >= limit:
            break

        # ユーザー検索
        page.goto(f"https://twitter.com/search?q={kw}&f=user&src=typed_query", timeout=30000)
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 4))

        for _ in range(3):  # スクロールして追加ロード
            user_cells = page.query_selector_all('[data-testid="UserCell"]')
            for cell in user_cells:
                if len(leads) >= limit:
                    break
                try:
                    name_el   = cell.query_selector('[data-testid="UserName"]')
                    bio_el    = cell.query_selector('[data-testid="UserDescription"]')
                    follow_el = cell.query_selector('[data-testid="UserFollowersCount"]')

                    if not name_el:
                        continue

                    name_text = name_el.inner_text()
                    lines = [l.strip() for l in name_text.split("\n") if l.strip()]
                    display_name = lines[0] if lines else ""
                    username     = lines[1].lstrip("@") if len(lines) > 1 else ""

                    if not username or username in seen:
                        continue

                    bio = bio_el.inner_text() if bio_el else ""
                    follower_text = follow_el.inner_text() if follow_el else "0"
                    follower_count = _parse_follower_count(follower_text)

                    if not (follower_min <= follower_count <= follower_max):
                        continue

                    seen.add(username)
                    leads.append(Lead(
                        platform="twitter",
                        account_id=username,
                        username=username,
                        display_name=display_name,
                        bio=bio,
                        follower_count=follower_count,
                        email=_extract_email_from_bio(bio),
                        content_type=_guess_content_type(bio, username),
                        profile_url=f"https://twitter.com/{username}",
                    ))
                except Exception:
                    continue

            page.keyboard.press("End")
            time.sleep(random.uniform(1.5, 3))

    return leads


# ─── Instagram ────────────────────────────────────────────

def scrape_instagram(
    page: Page,
    hashtags: list[str],
    follower_min: int,
    follower_max: int,
    limit: int = 40,
) -> list[Lead]:
    leads = []
    seen = set()

    for tag in hashtags:
        if len(leads) >= limit:
            break

        page.goto(f"https://www.instagram.com/explore/tags/{tag}/", timeout=30000)
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(3, 5))

        # 投稿をクリックして投稿者を収集
        posts = page.query_selector_all("article a")[:20]
        post_urls = []
        for p in posts:
            href = p.get_attribute("href")
            if href and "/p/" in href:
                post_urls.append("https://www.instagram.com" + href)

        for post_url in post_urls:
            if len(leads) >= limit:
                break
            try:
                page.goto(post_url, timeout=20000)
                page.wait_for_load_state("networkidle")
                time.sleep(random.uniform(2, 4))

                # 投稿者のプロフィールリンクを取得
                author_el = page.query_selector('header a[role="link"]')
                if not author_el:
                    continue
                username = author_el.get_attribute("href").strip("/").split("/")[-1]
                if not username or username in seen:
                    continue

                # プロフィールページへ
                page.goto(f"https://www.instagram.com/{username}/", timeout=20000)
                page.wait_for_load_state("networkidle")
                time.sleep(random.uniform(2, 3))

                # フォロワー数
                follower_el = page.query_selector('a[href$="/followers/"] span, span[title]')
                follower_text = follower_el.get_attribute("title") or follower_el.inner_text() if follower_el else "0"
                follower_count = _parse_follower_count(follower_text)

                if not (follower_min <= follower_count <= follower_max):
                    continue

                # プロフィール文
                bio_el = page.query_selector('div.-vDIg span, section > div > div > span')
                bio = bio_el.inner_text() if bio_el else ""

                # 表示名
                name_el = page.query_selector('h1, h2')
                display_name = name_el.inner_text() if name_el else username

                seen.add(username)
                leads.append(Lead(
                    platform="instagram",
                    account_id=username,
                    username=username,
                    display_name=display_name,
                    bio=bio,
                    follower_count=follower_count,
                    email=_extract_email_from_bio(bio),
                    content_type=_guess_content_type(bio, username),
                    profile_url=f"https://www.instagram.com/{username}/",
                ))
            except Exception:
                continue

    return leads
