"""
crowdworks.py - CrowdWorks の案件スクレイプ＆自動応募
"""
import re
import time
import random
from dataclasses import dataclass
from playwright.sync_api import Page


@dataclass
class Job:
    platform: str
    job_id: str
    title: str
    description: str
    budget_text: str
    budget_min: int
    budget_max: int
    job_type: str    # "task" | "project" | "contest"
    url: str
    client_name: str = ""


def _parse_budget(text: str) -> tuple[int, int]:
    """'5,000円〜10,000円' '固定10,000円' などを (min, max) に変換"""
    nums = re.findall(r"[\d,]+", text.replace("，", ","))
    nums = [int(n.replace(",", "")) for n in nums if n]
    if not nums:
        return (0, 0)
    if len(nums) == 1:
        return (nums[0], nums[0])
    return (nums[0], nums[-1])


def scrape_crowdworks(
    page: Page,
    keywords: list[str],
    budget_min: int = 0,
    limit: int = 30,
) -> list[Job]:
    jobs = []
    seen = set()

    for kw in keywords:
        if len(jobs) >= limit:
            break

        page.goto(
            f"https://crowdworks.jp/public/jobs/search?order=score&hide_expired=1&q={kw}",
            timeout=30000,
        )
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 4))

        # 複数ページ
        for page_num in range(1, 4):
            if len(jobs) >= limit:
                break

            rows = page.query_selector_all(".job_offer__item, article.job-offer-item")
            if not rows:
                # 別セレクタ試行
                rows = page.query_selector_all("li.search-result-item")

            for row in rows:
                if len(jobs) >= limit:
                    break
                try:
                    # タイトル・URL
                    link = row.query_selector("a.job_offer__title, a.job-offer-title, h3 a, h2 a")
                    if not link:
                        continue
                    title = link.inner_text().strip()
                    href  = link.get_attribute("href") or ""
                    if not href:
                        continue
                    url = href if href.startswith("http") else "https://crowdworks.jp" + href

                    job_id = re.search(r"/jobs/(\d+)", url)
                    job_id = job_id.group(1) if job_id else url

                    if job_id in seen:
                        continue

                    # 予算
                    budget_el = row.query_selector(".job_offer__reward, .reward, .budget")
                    budget_text = budget_el.inner_text().strip() if budget_el else ""
                    bmin, bmax = _parse_budget(budget_text)

                    if budget_min > 0 and bmax > 0 and bmax < budget_min:
                        continue

                    # 案件種別
                    job_type = "project"
                    if "タスク" in title or "task" in url:
                        job_type = "task"
                    elif "コンテスト" in title:
                        job_type = "contest"

                    seen.add(job_id)
                    jobs.append(Job(
                        platform="crowdworks",
                        job_id=job_id,
                        title=title,
                        description="",   # 詳細は apply 時に取得
                        budget_text=budget_text,
                        budget_min=bmin,
                        budget_max=bmax,
                        job_type=job_type,
                        url=url,
                    ))
                except Exception:
                    continue

            # 次のページへ
            next_btn = page.query_selector("a[rel='next'], .pagination a:has-text('次へ'), li.next a")
            if next_btn:
                next_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(random.uniform(2, 3))
            else:
                break

    return jobs


def apply_crowdworks(page: Page, job: Job, proposal: str, price: int = 0) -> bool:
    """
    CrowdWorksの案件に応募する。
    proposal: 提案文 (Claude生成)
    price: 希望単価 (プロジェクト型のみ, 0=スキップ)
    成功: True
    """
    try:
        page.goto(job.url, timeout=20000)
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 4))

        # 案件詳細取得 (詳細説明文)
        desc_el = page.query_selector(".job_offer__description, .description, .job-description")
        if desc_el:
            job.description = desc_el.inner_text()[:1000]

        # 「応募する」ボタン
        apply_btn = page.query_selector(
            "a:has-text('応募する'), button:has-text('応募する'), "
            "a:has-text('提案する'), button:has-text('提案する')"
        )
        if not apply_btn:
            print(f"  [SKIP] {job.title[:40]} : 応募ボタンなし")
            return False

        apply_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 3))

        # 提案文入力
        textarea = page.query_selector(
            "textarea[name*='message'], textarea[name*='proposal'], "
            "textarea[placeholder*='提案'], textarea.proposal-textarea"
        )
        if not textarea:
            print(f"  [SKIP] {job.title[:40]} : 入力欄なし")
            return False

        textarea.fill(proposal)
        time.sleep(random.uniform(0.5, 1))

        # 希望単価入力 (プロジェクト型)
        if price > 0:
            price_input = page.query_selector(
                "input[name*='price'], input[name*='reward'], input[type='number']"
            )
            if price_input:
                price_input.fill(str(price))
                time.sleep(0.3)

        # 送信ボタン
        submit_btn = page.query_selector(
            "button[type='submit']:has-text('提案'), "
            "button[type='submit']:has-text('応募'), "
            "input[type='submit']"
        )
        if not submit_btn:
            print(f"  [SKIP] {job.title[:40]} : 送信ボタンなし")
            return False

        submit_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 3))

        # 成功確認
        success = page.query_selector(".alert-success, .notice, .flash--success")
        if success or "応募" in (page.query_selector("h1, h2, .heading") or page.locator("body")).inner_text()[:100]:
            print(f"  [OK]   {job.title[:40]} に応募完了")
            return True

        print(f"  [OK?]  {job.title[:40]} : ページ遷移済み (要確認)")
        return True

    except Exception as e:
        print(f"  [ERR]  {job.title[:40]} : {e}")
        return False
