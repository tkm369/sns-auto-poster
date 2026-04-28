"""
DLSite販売戦略アドバイザー
Gemini APIを使って、DLSiteで売れるゲームの戦略を分析・提案する
"""
import json
import re
import time
import google.generativeai as genai


def _call(model, prompt: str, log=print, local_client=None) -> str:
    if local_client is not None:
        from local_model import generate_local
        return generate_local(prompt, base_url=local_client["base_url"],
                              max_tokens=8000, log=log)
    for attempt in range(3):
        try:
            result = []
            for chunk in model.generate_content(prompt, stream=True, request_options={"timeout": 60}):
                text = chunk.text or ""
                result.append(text)
            return re.sub(r"```[a-z]*\n?", "", "".join(result)).replace("```", "").strip()
        except Exception as e:
            if attempt < 2:
                wait = 4 + attempt * 3
                log(f"  API呼び出しエラー: {e} → {wait}秒後にリトライ...")
                time.sleep(wait)
            else:
                raise


def _parse_json(model, prompt: str, log=print, max_retry=3, local_client=None) -> dict:
    for attempt in range(max_retry):
        raw = _call(model, prompt, log, local_client=local_client)
        m = re.search(r'\{[\s\S]+\}', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError as e:
                log(f"  JSON解析エラー (試行{attempt+1}): {e}")
        if attempt < max_retry - 1:
            time.sleep(2)
    raise ValueError("JSON生成に失敗しました")


# ── 1. ジャンル別市場分析 ──────────────────────────────────────────
def analyze_market(model, game_type: str, genre: str, adult: bool, log=print, local_client=None) -> dict:
    """ゲームタイプ×ジャンルのDLSite市場を分析"""
    log(f"\n[市場分析] {game_type} / {genre}\n")
    adult_note = "成人向け（R18）" if adult else "全年齢向け"
    prompt = f"""あなたはDLSiteの同人ゲーム販売に詳しい市場アナリストです。
以下のゲームカテゴリのDLSite市場について詳しく分析してください。

ゲームタイプ: {game_type}
ジャンル: {genre}
対象年齢: {adult_note}

DLSiteでの実際の販売傾向・人気作品の特徴・売れる要素を元に分析し、
以下のJSON形式のみで出力してください:
{{
  "market_overview": "このカテゴリの市場規模・競合状況（3〜4文）",
  "avg_price": "推奨価格帯（例: 1,100〜2,200円）",
  "top_selling_elements": [
    "売れる要素1（具体的に）",
    "売れる要素2",
    "売れる要素3",
    "売れる要素4",
    "売れる要素5"
  ],
  "trending_tags": ["人気タグ1", "タグ2", "タグ3", "タグ4", "タグ5", "タグ6", "タグ7", "タグ8"],
  "avoid_elements": ["避けるべき要素1", "要素2", "要素3"],
  "difficulty": "競合の激しさ（低/中/高）",
  "revenue_potential": "月間収益ポテンシャル（例: 5〜30万円）",
  "success_examples": "このジャンルで成功している作品の特徴（2〜3文）",
  "unique_advice": "このジャンルで勝つための独自アドバイス（3〜4文）"
}}"""
    return _parse_json(model, prompt, log, local_client=local_client)


# ── 2. 作品ページ最適化アドバイス ─────────────────────────────────
def generate_page_strategy(model, concept: dict, game_type: str,
                           adult: bool, log=print, local_client=None) -> dict:
    """DLSiteの作品ページを最適化するための戦略を生成"""
    log("\n[販売ページ戦略] 最適化中...\n")
    title = concept.get("title", "作品タイトル")
    tagline = concept.get("tagline", "")
    setting = concept.get("setting", "")
    adult_note = "成人向け（R18）" if adult else "全年齢向け"

    prompt = f"""あなたはDLSiteで数十本のゲームを販売してきたベテランクリエイターです。
以下のゲームのDLSite販売ページを最適化するアドバイスをしてください。

タイトル: {title}
キャッチコピー: {tagline}
世界観: {setting}
ゲームタイプ: {game_type}
対象年齢: {adult_note}

以下のJSON形式のみで出力してください:
{{
  "recommended_title": "DLSiteで売れるタイトル案（SEO・インパクト重視）",
  "catchcopy": "販売ページ用キャッチコピー（30字以内、刺さる一言）",
  "description_hook": "作品説明の冒頭文（最初の2〜3文、購入意欲を高める）",
  "key_features": [
    "特徴・見どころ1（箇条書きで掲載する内容）",
    "特徴2",
    "特徴3",
    "特徴4",
    "特徴5"
  ],
  "recommended_tags": ["DLSiteタグ1", "タグ2", "タグ3", "タグ4", "タグ5", "タグ6"],
  "price_strategy": "価格設定戦略と理由",
  "thumbnail_advice": "サムネイル・表紙イラストで意識すべきポイント（3〜4文）",
  "release_timing": "リリースに適した時期・曜日とその理由",
  "campaign_ideas": ["プロモーション案1", "案2", "案3"]
}}"""
    return _parse_json(model, prompt, log, local_client=local_client)


# ── 3. 競合分析・差別化戦略 ───────────────────────────────────────
def generate_differentiation(model, genre: str, game_type: str, log=print, local_client=None) -> dict:
    """競合との差別化ポイントを提案"""
    log("\n[差別化戦略] 分析中...\n")
    prompt = f"""DLSiteで{game_type}（{genre}）を販売する際の競合分析と差別化戦略を提案してください。

以下のJSON形式のみで出力してください:
{{
  "market_gaps": [
    "まだ誰もやっていない・少ないニッチ1",
    "ニッチ2",
    "ニッチ3"
  ],
  "differentiation_points": [
    "差別化ポイント1（具体的な実装アイデア付き）",
    "差別化ポイント2",
    "差別化ポイント3"
  ],
  "hook_ideas": [
    "購買意欲を刺激するフック・ギミック案1",
    "案2",
    "案3"
  ],
  "volume_strategy": "ボリューム・プレイ時間の最適解（DLSiteユーザーの期待値）",
  "sequel_potential": "続編・DLC・シリーズ展開のアドバイス",
  "cross_sell": "抱き合わせ・バンドル販売の提案"
}}"""
    return _parse_json(model, prompt, log, local_client=local_client)


# ── 4. 年収目標達成プラン ─────────────────────────────────────────
def generate_annual_plan(model, target_income: int, log=print, local_client=None) -> dict:
    """年間収益目標を達成するためのロードマップ"""
    log(f"\n[年収プラン] 目標: {target_income:,}円\n")
    prompt = f"""DLSiteで同人ゲームを販売して年間{target_income:,}円を稼ぐための
具体的なロードマップを作ってください。

以下のJSON形式のみで出力してください:
{{
  "monthly_target": "月間売上目標",
  "product_plan": [
    {{
      "quarter": "Q1（1〜3月）",
      "title": "リリース作品タイプ",
      "target_sales": "目標販売本数・金額",
      "priority_actions": ["アクション1", "アクション2"]
    }},
    {{
      "quarter": "Q2（4〜6月）",
      "title": "リリース作品タイプ",
      "target_sales": "目標販売本数・金額",
      "priority_actions": ["アクション1", "アクション2"]
    }},
    {{
      "quarter": "Q3（7〜9月）",
      "title": "リリース作品タイプ",
      "target_sales": "目標販売本数・金額",
      "priority_actions": ["アクション1", "アクション2"]
    }},
    {{
      "quarter": "Q4（10〜12月）",
      "title": "リリース作品タイプ",
      "target_sales": "目標販売本数・金額",
      "priority_actions": ["アクション1", "アクション2"]
    }}
  ],
  "key_milestones": ["マイルストーン1", "マイルストーン2", "マイルストーン3"],
  "risk_factors": ["リスク1と対策", "リスク2と対策"],
  "quick_wins": ["今すぐできる収益化アクション1", "アクション2", "アクション3"],
  "genre_recommendation": "このパイプラインで最も稼ぎやすいジャンル推薦と理由",
  "realistic_assessment": "現実的な達成確率と成功条件（正直な評価）"
}}"""
    return _parse_json(model, prompt, log, local_client=local_client)


# ── 5. フルレポート生成（Markdown） ──────────────────────────────
def generate_full_report(model, concept: dict, game_type: str, genre: str,
                         adult: bool, log=print, local_client=None) -> str:
    """作品ごとのDLSite販売戦略レポートをMarkdownで生成"""
    log("\n[販売戦略レポート] 生成中...\n")

    market = analyze_market(model, game_type, genre, adult, log, local_client=local_client)
    page = generate_page_strategy(model, concept, game_type, adult, log, local_client=local_client)
    diff = generate_differentiation(model, genre, game_type, log, local_client=local_client)

    title = concept.get("title", "作品タイトル")

    lines = [
        f"# DLSite販売戦略レポート — {title}",
        "",
        f"**ゲームタイプ:** {game_type}  ",
        f"**ジャンル:** {genre}  ",
        f"**対象:** {'成人向け（R18）' if adult else '全年齢向け'}  ",
        "",
        "---",
        "",
        "## 📊 市場分析",
        "",
        f"**市場概況:** {market.get('market_overview', '')}",
        "",
        f"**推奨価格帯:** {market.get('avg_price', '')}",
        f"**競合の激しさ:** {market.get('difficulty', '')}",
        f"**収益ポテンシャル:** {market.get('revenue_potential', '')}",
        "",
        "### 売れる要素 TOP5",
    ]
    for i, e in enumerate(market.get("top_selling_elements", []), 1):
        lines.append(f"{i}. {e}")

    lines += [
        "",
        "### 人気タグ",
        " ".join(f"`{t}`" for t in market.get("trending_tags", [])),
        "",
        "### 避けるべき要素",
    ]
    for e in market.get("avoid_elements", []):
        lines.append(f"- {e}")

    lines += [
        "",
        f"**成功作品の特徴:** {market.get('success_examples', '')}",
        "",
        f"**勝つためのアドバイス:** {market.get('unique_advice', '')}",
        "",
        "---",
        "",
        "## 🏪 販売ページ最適化",
        "",
        f"**推奨タイトル:** {page.get('recommended_title', '')}",
        f"**キャッチコピー:** {page.get('catchcopy', '')}",
        "",
        "### 作品説明冒頭文（そのまま使えます）",
        f"> {page.get('description_hook', '')}",
        "",
        "### 見どころ・特徴（箇条書き用）",
    ]
    for f_ in page.get("key_features", []):
        lines.append(f"- {f_}")

    lines += [
        "",
        "### 推奨DLSiteタグ",
        " ".join(f"`{t}`" for t in page.get("recommended_tags", [])),
        "",
        f"**価格戦略:** {page.get('price_strategy', '')}",
        "",
        f"**サムネイル・表紙のポイント:** {page.get('thumbnail_advice', '')}",
        "",
        f"**リリースタイミング:** {page.get('release_timing', '')}",
        "",
        "### プロモーション案",
    ]
    for c in page.get("campaign_ideas", []):
        lines.append(f"- {c}")

    lines += [
        "",
        "---",
        "",
        "## 🎯 差別化戦略",
        "",
        "### 市場の空きニッチ",
    ]
    for g in diff.get("market_gaps", []):
        lines.append(f"- {g}")

    lines += [
        "",
        "### 差別化ポイント",
    ]
    for d in diff.get("differentiation_points", []):
        lines.append(f"- {d}")

    lines += [
        "",
        "### 購買意欲を上げるフック・ギミック",
    ]
    for h in diff.get("hook_ideas", []):
        lines.append(f"- {h}")

    lines += [
        "",
        f"**ボリューム・プレイ時間の最適解:** {diff.get('volume_strategy', '')}",
        f"**続編・DLC展開:** {diff.get('sequel_potential', '')}",
        f"**バンドル販売:** {diff.get('cross_sell', '')}",
        "",
        "---",
        "",
        "## 📝 このレポートの使い方",
        "",
        "1. **推奨タイトル・キャッチコピー** をDLSiteの登録タイトルにそのまま使う",
        "2. **作品説明冒頭文** を作品ページの最初に貼り付ける",
        "3. **推奨タグ** をすべて設定する",
        "4. **サムネイルのポイント** を意識してAI画像を生成・選定する",
        "5. **差別化ポイント** を実装・強調してライバルと差をつける",
        "",
        "_Generated by ゲーム自動生成パイプライン_",
    ]

    return "\n".join(lines)


# ── スタンドアロン分析（タブ用） ─────────────────────────────────
def run_market_analysis(game_type: str, genre: str, adult: bool,
                        target_income: int, api_key: str, log=print) -> str:
    """app.pyのDLSiteタブから呼ばれるエントリポイント"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    log("━━━ DLSite市場分析 開始 ━━━")
    log(f"カテゴリ: {game_type} / {genre}")
    log(f"目標年収: {target_income:,}円")
    log("")

    market = analyze_market(model, game_type, genre, adult, log)
    diff = generate_differentiation(model, genre, game_type, log)
    annual = generate_annual_plan(model, target_income, log)

    lines = [
        f"# DLSite市場分析 — {game_type}（{genre}）",
        "",
        "---",
        "",
        "## 📊 市場概況",
        "",
        market.get("market_overview", ""),
        "",
        f"| 項目 | 内容 |",
        f"|---|---|",
        f"| 推奨価格帯 | {market.get('avg_price', '')} |",
        f"| 競合の激しさ | {market.get('difficulty', '')} |",
        f"| 収益ポテンシャル | {market.get('revenue_potential', '')} |",
        "",
        "### ✅ 売れる要素 TOP5",
    ]
    for i, e in enumerate(market.get("top_selling_elements", []), 1):
        lines.append(f"{i}. {e}")

    lines += [
        "",
        "### 🏷️ 人気タグ（全部設定しよう）",
        " ".join(f"`{t}`" for t in market.get("trending_tags", [])),
        "",
        "### ❌ 避けるべき要素",
    ]
    for e in market.get("avoid_elements", []):
        lines.append(f"- {e}")

    lines += [
        "",
        f"**成功作品の特徴:** {market.get('success_examples', '')}",
        "",
        f"**勝つためのアドバイス:** {market.get('unique_advice', '')}",
        "",
        "---",
        "",
        "## 🎯 差別化戦略",
        "",
        "### 空きニッチ（ライバルが少ない穴場）",
    ]
    for g in diff.get("market_gaps", []):
        lines.append(f"- {g}")

    lines += [
        "",
        "### 差別化ポイント",
    ]
    for d in diff.get("differentiation_points", []):
        lines.append(f"- {d}")

    lines += [
        "",
        f"**ボリューム最適解:** {diff.get('volume_strategy', '')}",
        f"**続編・DLC展開:** {diff.get('sequel_potential', '')}",
        "",
        "---",
        "",
        f"## 💰 年収{target_income:,}円 達成ロードマップ",
        "",
        f"**月間目標:** {annual.get('monthly_target', '')}",
        "",
    ]

    for q in annual.get("product_plan", []):
        lines += [
            f"### {q.get('quarter', '')}",
            f"- **作品:** {q.get('title', '')}",
            f"- **目標:** {q.get('target_sales', '')}",
        ]
        for a in q.get("priority_actions", []):
            lines.append(f"  - {a}")
        lines.append("")

    lines += [
        "### 🚀 今すぐできること",
    ]
    for qw in annual.get("quick_wins", []):
        lines.append(f"- {qw}")

    lines += [
        "",
        f"**推奨ジャンル:** {annual.get('genre_recommendation', '')}",
        "",
        f"**現実的な評価:** {annual.get('realistic_assessment', '')}",
        "",
        "---",
        "",
        "### ⚠️ リスクと対策",
    ]
    for r in annual.get("risk_factors", []):
        lines.append(f"- {r}")

    return "\n".join(lines)
