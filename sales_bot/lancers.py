"""
lancers.py - Lancers の案件スクレイプ＆自動応募
"""
import re
import time
import random
from dataclasses import dataclass
from playwright.sync_api import Page
from crowdworks import Job  # 同じデータクラスを流用


def _parse_budget(text: str) -> tuple[int, int]:
    nums = re.findall(r"[\d,]+", text.replace("，", ","))
    nums = [int(n.replace(",", "")) for n in nums if n]
    if not nums:
        return (0, 0)
    if len(nums) == 1:
        return (nums[0], nums[0])
    return (nums[0], nums[-1])


def scrape_lancers(
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
            f"https://www.lancers.jp/work/search?keyword={kw}&open=1&sort=score",
            timeout=30000,
        )
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 4))

        for page_num in range(1, 4):
            if len(jobs) >= limit:
                break

            rows = page.query_selector_all(".work-item, article.work-list-item, li.search-list__item")

            for row in rows:
                if len(jobs) >= limit:
                    break
                try:
                    link = row.query_selector("a.work-item__title, a.work-title, h3 a, h2 a")
                    if not link:
                        continue
                    title = link.inner_text().strip()
                    href  = link.get_attribute("href") or ""
                    if not href:
                        continue
                    url = href if href.startswith("http") else "https://www.lancers.jp" + href

                    job_id = re.search(r"/work/detail/(\d+)", url)
                    job_id = job_id.group(1) if job_id else url

                    if job_id in seen:
                        continue

                    budget_el = row.query_selector(".work-item__price, .price, .budget")
                    budget_text = budget_el.inner_text().strip() if budget_el else ""
                    bmin, bmax = _parse_budget(budget_text)

                    if budget_min > 0 and bmax > 0 and bmax < budget_min:
                        continue

                    job_type = "project"
                    if "タスク" in title:
                        job_type = "task"
                    elif "コンテスト" in title:
                        job_type = "contest"

                    seen.add(job_id)
                    jobs.append(Job(
                        platform="lancers",
                        job_id=job_id,
                        title=title,
                        description="",
                        budget_text=budget_text,
                        budget_min=bmin,
                        budget_max=bmax,
                        job_type=job_type,
                        url=url,
                    ))
                except Exception:
                    continue

            next_btn = page.query_selector("a[rel='next'], .pagination a:has-text('次へ'), li.next a")
            if next_btn:
                next_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(random.uniform(2, 3))
            else:
                break

    return jobs


def apply_lancers(page: Page, job: Job, proposal: str, price: int = 0) -> bool:
    try:
        page.goto(job.url, timeout=20000)
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 4))

        desc_el = page.query_selector(".work-detail__description, .description, #work-description")
        if desc_el:
            job.description = desc_el.inner_text()[:1000]

        apply_btn = page.query_selector(
            "a:has-text('提案する'), button:has-text('提案する'), "
            "a:has-text('応募する'), button:has-text('応募する')"
        )
        if not apply_btn:
            print(f"  [SKIP] {job.title[:40]} : 応募ボタンなし")
            return False

        apply_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 3))

        textarea = page.query_selector(
            "textarea[name*='message'], textarea[name*='proposal'], "
            "textarea[name*='comment'], textarea.proposal__textarea"
        )
        if not textarea:
            print(f"  [SKIP] {job.title[:40]} : 入力欄なし")
            return False

        textarea.fill(proposal)
        time.sleep(random.uniform(0.5, 1))

        if price > 0:
            price_input = page.query_selector(
                "input[name*='price'], input[name*='amount'], input[type='number']"
            )
            if price_input:
                price_input.fill(str(price))
                time.sleep(0.3)

        submit_btn = page.query_selector(
            "button[type='submit']:has-text('提案'), "
            "button[type='submit']:has-text('送信'), "
            "input[type='submit']"
        )
        if not submit_btn:
            print(f"  [SKIP] {job.title[:40]} : 送信ボタンなし")
            return False

        submit_btn.click()
        page.wait_for_load_state("networkidle")
        time.sleep(random.uniform(2, 3))

        print(f"  [OK]   {job.title[:40]} に応募完了")
        return True

    except Exception as e:
        print(f"  [ERR]  {job.title[:40]} : {e}")
        return False
