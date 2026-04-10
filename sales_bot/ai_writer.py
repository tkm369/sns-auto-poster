"""
ai_writer.py - Claude APIでパーソナライズ営業文章を生成
"""
import anthropic
from config import (
    ANTHROPIC_API_KEY, MY_NAME, MY_SERVICE,
    MY_PORTFOLIO_URL, MY_CONTACT
)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def generate_dm(
    platform: str,
    username: str,
    display_name: str,
    bio: str,
    follower_count: int,
    content_type: str,   # "gaming", "vlog", "business", "lifestyle" など
) -> str:
    """
    ターゲットの情報を元にパーソナライズされた営業DMを生成する。
    platform: "twitter" | "instagram" | "email"
    """
    portfolio_line = f"ポートフォリオ: {MY_PORTFOLIO_URL}" if MY_PORTFOLIO_URL else ""
    contact_line   = f"連絡先: {MY_CONTACT}" if MY_CONTACT else ""

    length_guide = {
        "twitter":   "120文字以内",
        "instagram": "150文字以内",
        "email":     "300文字以内",
    }.get(platform, "150文字以内")

    prompt = f"""あなたは{MY_SERVICE}フリーランサーの{MY_NAME}です。
以下のSNSアカウントに営業DMを送ります。

【相手の情報】
- ユーザー名: @{username} ({display_name})
- プロフィール: {bio[:200] if bio else "不明"}
- フォロワー数: {follower_count:,}
- コンテンツ系統: {content_type}
- プラットフォーム: {platform}

【あなたのサービス】
- サービス内容: {MY_SERVICE}
- {portfolio_line}
- {contact_line}

【要件】
- {length_guide}に収める
- 相手のコンテンツ内容に触れて「あなただから連絡した」感を出す
- 具体的な価値提案を1つ入れる (例: サムネ品質UP、編集時間の削減、再生数向上)
- 売り込み感を抑え、軽く提案する口調
- 敬語、フランクすぎない
- URLや署名は含めない (後で追加する)
- DMの本文だけ出力すること (説明・前置き不要)
"""

    message = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    text = message.content[0].text.strip()

    # 署名を追加
    suffix_parts = []
    if MY_PORTFOLIO_URL and platform == "email":
        suffix_parts.append(f"\nポートフォリオ: {MY_PORTFOLIO_URL}")
    if MY_CONTACT and platform != "email":
        suffix_parts.append(f"\n{MY_CONTACT}")

    return text + "".join(suffix_parts)


def generate_proposal(
    platform: str,          # "crowdworks" | "lancers"
    job_title: str,
    job_description: str,
    budget_text: str,
    job_type: str,
) -> str:
    """
    クラウドソーシング案件への提案文を生成する。
    platform: "crowdworks" | "lancers"
    """
    portfolio_line = f"ポートフォリオ: {MY_PORTFOLIO_URL}" if MY_PORTFOLIO_URL else ""
    desc_excerpt = job_description[:500] if job_description else "（詳細不明）"
    platform_name = {"crowdworks": "クラウドワークス", "lancers": "ランサーズ"}.get(platform, platform)

    prompt = f"""あなたは{MY_SERVICE}フリーランサーの{MY_NAME}です。
{platform_name} の以下の案件に提案文を送ります。

【案件情報】
- タイトル: {job_title}
- 案件種別: {job_type}
- 予算: {budget_text}
- 説明:
{desc_excerpt}

【あなたのサービス】
- サービス: {MY_SERVICE}
- {portfolio_line}

【要件】
- 400文字以内
- 案件内容を理解していることが伝わる書き方にする
- 自分の強みや経験を1〜2点具体的にアピール
- 納期・品質への配慮を述べる
- 「ぜひご相談ください」などの行動喚起で締める
- 「いつもお世話になっております」などの決まり文句は不要
- 提案文本文だけ出力すること (説明・前置き不要)
"""

    message = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()


def generate_email(
    username: str,
    display_name: str,
    bio: str,
    follower_count: int,
    content_type: str,
    subject_only: bool = False,
) -> tuple[str, str]:
    """件名と本文をタプルで返す"""
    body = generate_dm(
        platform="email",
        username=username,
        display_name=display_name,
        bio=bio,
        follower_count=follower_count,
        content_type=content_type,
    )

    subject_prompt = f"""以下の動画編集営業メールに適切な件名を1行で作成してください。
読んでもらえる件名にし、スパムっぽくしない。20文字以内。
件名だけ出力:

{body[:200]}"""

    subject_msg = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[{"role": "user", "content": subject_prompt}]
    )
    subject = subject_msg.content[0].text.strip().strip("「」【】")

    if subject_only:
        return subject, ""
    return subject, body
