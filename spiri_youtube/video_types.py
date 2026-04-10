"""
video_types.py — 動画の「型」定義

各型は以下を持つ:
  - id          : CLIで指定するキー
  - label       : 表示名
  - description : 型の説明
  - system_prompt_extra : script_generator の SYSTEM プロンプトに追加する指示
  - script_structure    : 台本の構成指示（USER プロンプトに含める）
  - tts_voice    : 推奨 edge-tts 音声
  - tts_rate     : 読み上げ速度 ("+0%", "-10%" など edge-tts 形式)
  - bg_keywords  : Pexels 背景動画検索キーワードのリスト（ランダムに選択）
  - subtitle_style: 字幕スタイル辞書（ASS/drawtext パラメータ）
  - title_style  : タイトルテロップスタイル辞書
  - default_duration_min: デフォルト動画尺（分）
"""
from __future__ import annotations
import random
import sys
from dataclasses import dataclass, field
from typing import Optional

# Windows cp932対策
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class SubtitleStyle:
    fontname:        str   = "Noto Sans CJK JP"
    fontsize:        int   = 52
    primary_colour:  str   = "&H00FFFFFF"   # 白
    outline_colour:  str   = "&H00000000"   # 黒縁
    back_colour:     str   = "&H80000000"   # 半透明黒背景
    bold:            int   = -1             # -1=太字
    outline:         float = 3.0
    shadow:          float = 1.0
    margin_v:        int   = 60
    alignment:       int   = 2             # 2=下中央


@dataclass
class TitleStyle:
    fontsize:      int  = 64
    fontcolor:     str  = "white"
    bordercolor:   str  = "black"
    borderw:       int  = 3
    y_ratio:       float = 0.12   # 画面高さに対する Y位置の割合
    duration_sec:  float = 5.0    # 表示秒数
    box:           bool  = False  # 背景ボックス
    boxcolor:      str   = "black@0.5"


@dataclass
class VideoType:
    id:                    str
    label:                 str
    description:           str
    system_prompt_extra:   str
    script_structure:      str
    tts_voice:             str   = "ja-JP-NanamiNeural"
    tts_rate:              str   = "+0%"
    bg_keywords:           list[str] = field(default_factory=list)
    subtitle_style:        SubtitleStyle = field(default_factory=SubtitleStyle)
    title_style:           TitleStyle    = field(default_factory=TitleStyle)
    default_duration_min:  int  = 8

    # ── ショート専用フィールド ─────────────────────────────
    # shorts_script_structure: None の場合は共通の system_prompt_extra を流用し
    #   台本尺だけ shorts_duration_sec に変更する
    shorts_script_structure: str = ""
    shorts_duration_sec:     int = 50       # ショートの目標尺（秒）
    shorts_tts_rate:         str = "+5%"    # ショートは少し早め
    shorts_subtitle_style:   SubtitleStyle = field(
        default_factory=lambda: SubtitleStyle(
            fontsize       = 68,
            primary_colour = "&H00FFFFFF",
            outline_colour = "&H00000000",
            back_colour    = "&HAA000000",
            bold           = -1,
            outline        = 4.0,
            shadow         = 2.0,
            margin_v       = 120,
            alignment      = 5,   # 5=中央中央（Shorts向け）
        )
    )
    shorts_title_style:      TitleStyle = field(
        default_factory=lambda: TitleStyle(
            fontsize     = 72,
            fontcolor    = "white",
            bordercolor  = "black",
            borderw      = 4,
            y_ratio      = 0.08,
            duration_sec = 3.0,
            box          = True,
            boxcolor     = "black@0.55",
        )
    )

    def random_bg_keyword(self) -> str:
        return random.choice(self.bg_keywords) if self.bg_keywords else "cosmos meditation"

    def get_shorts_script_structure(self) -> str:
        """ショート台本構成を返す。型固有の定義がない場合は共通デフォルトを使用"""
        if self.shorts_script_structure:
            return self.shorts_script_structure
        return f"""
構成（必ず守ること）:
[フック 5秒]  冒頭1文で「え、それ知らなかった！」と思わせる衝撃の一言
[本編 40秒]   テーマの核心だけを凝縮して伝える（1〜3ポイント）
[締め 5秒]    「詳しくは長編動画で」または「保存して後でまた見てください」
全体で約{self.shorts_duration_sec}秒で読み終わる分量にすること。
"""


# ════════════════════════════════════════════════════════
# 型定義
# ════════════════════════════════════════════════════════

TYPES: dict[str, VideoType] = {}

def _reg(vt: VideoType) -> VideoType:
    TYPES[vt.id] = vt
    return vt


# ── 1. アファメーション ──────────────────────────────────
_reg(VideoType(
    id    = "affirmation",
    label = "✨ アファメーション",
    description = "ゆっくり・繰り返し・心に刻む宣言動画。睡眠前や朝の習慣向け。",

    system_prompt_extra = """
【アファメーション動画の特別ルール】
- 「私は〜です」「私は〜を引き寄せています」の断言形を多用
- 1センテンスを極めて短く（10〜20文字）
- 同じフレーズを3回繰り返す構成を随所に入れる
- 聴くだけで潜在意識に刻まれるリズム感を重視
- 冒頭に「目を閉じて、深呼吸してください」と誘導
""",

    script_structure = """
構成（必ず守ること）:
[導入 30秒] 深呼吸の誘導 → 今からアファメーションを行う宣言
[本編 7分]  テーマに沿ったアファメーション文を30〜40個
             ※ 各文を2〜3回繰り返す、ゆったりしたテンポで
[締め 30秒] 「あなたはすでに受け取っています」で締める
""",

    tts_voice  = "ja-JP-NanamiNeural",
    tts_rate   = "-15%",   # ゆっくり読み上げ
    bg_keywords = [
        "golden light bokeh",
        "aurora peaceful",
        "soft clouds sunrise",
        "peaceful nature morning",
        "glowing particles abstract",
    ],
    subtitle_style = SubtitleStyle(
        fontsize       = 58,
        primary_colour = "&H00FFEEDD",   # 温かみのある白
        outline_colour = "&H00000000",
        bold           = -1,
        outline        = 2.0,
        margin_v       = 80,
    ),
    title_style = TitleStyle(
        fontsize    = 72,
        fontcolor   = "white",
        bordercolor = "black",
        borderw     = 3,
        y_ratio     = 0.10,
        duration_sec= 6.0,
    ),
    default_duration_min = 8,
))


# ── 2. スピ教育系 ────────────────────────────────────────
_reg(VideoType(
    id    = "education",
    label = "📖 スピ教育系",
    description = "スピリチュアルな知識・概念をわかりやすく解説する動画。",

    system_prompt_extra = """
【スピ教育系動画の特別ルール】
- 「〜とはどういう意味か」「〜の仕組み」を噛み砕いて解説するトーン
- 初心者にもわかる言葉を使う（難解な専門用語は必ず補足説明）
- 「実はこんな秘密があります」「多くの人が知らないこと」など好奇心を刺激する表現
- 箇条書きになる部分は「まず1つ目は〜、2つ目は〜」と口語で流す
- 最後に「まとめ」と「実践ヒント」を必ず入れる
""",

    script_structure = """
構成（必ず守ること）:
[フック 1分]   「あなたは〜を知っていますか？」で興味を引く衝撃的な事実
[解説本編 6分] テーマを3〜5つのポイントに分けて解説
               各ポイントに「具体的なエピソード or たとえ話」を添える
[実践 1分]     今日からできる簡単な実践方法を1〜2つ
[締め 30秒]    チャンネル登録を自然な流れで促す
""",

    tts_voice  = "ja-JP-NanamiNeural",
    tts_rate   = "+0%",
    bg_keywords = [
        "galaxy universe stars",
        "temple sacred light",
        "ancient mystical forest",
        "crystal glowing",
        "energy field abstract",
    ],
    subtitle_style = SubtitleStyle(
        fontsize       = 50,
        primary_colour = "&H00FFFFFF",
        outline_colour = "&H00000000",
        bold           = 0,
        outline        = 3.0,
        margin_v       = 55,
    ),
    title_style = TitleStyle(
        fontsize    = 68,
        fontcolor   = "white",
        bordercolor = "black",
        borderw     = 3,
        y_ratio     = 0.08,
        duration_sec= 5.0,
        box         = True,
        boxcolor    = "black@0.4",
    ),
    default_duration_min = 8,
))


# ── 3. 守護霊・天使メッセージ ─────────────────────────────
_reg(VideoType(
    id    = "message",
    label = "👼 守護霊・天使メッセージ",
    description = "守護霊や天使があなたに送るメッセージ形式。感情移入しやすい。",

    system_prompt_extra = """
【メッセージ動画の特別ルール】
- 守護霊 or 天使が「あなた」に直接語りかける一人称視点（「私はあなたのそばにいます」）
- 読者が泣けるほどの優しさと共感を込める
- 「今、あなたがこの動画を見ているのは偶然ではありません」でオープニング
- 「頑張ってきたあなたへ」「もう休んでいい」など労いのメッセージを多く含む
- 神秘的だが押しつけがましくない温かいトーン
""",

    script_structure = """
構成（必ず守ること）:
[出会い 30秒]  「この動画に引き寄せられたあなたへのメッセージです」
[本編 7分]     守護霊 / 天使からのメッセージを5〜7つ
               各メッセージに「あなたへの問いかけ」を1つ挟む
[締め 1分]     「あなたは一人じゃない」で締め → 感謝の言葉
""",

    tts_voice  = "ja-JP-NanamiNeural",
    tts_rate   = "-10%",
    bg_keywords = [
        "angel light heaven",
        "divine light bokeh",
        "soft white clouds",
        "golden hour peaceful",
        "ethereal glow abstract",
    ],
    subtitle_style = SubtitleStyle(
        fontsize       = 54,
        primary_colour = "&H00EEFFFF",   # 淡い水色
        outline_colour = "&H00334455",
        bold           = -1,
        outline        = 2.5,
        shadow         = 2.0,
        margin_v       = 70,
    ),
    title_style = TitleStyle(
        fontsize    = 70,
        fontcolor   = "#EEFFFF",
        bordercolor = "#334455",
        borderw     = 2,
        y_ratio     = 0.10,
        duration_sec= 6.0,
    ),
    default_duration_min = 8,
))


# ── 4. 引き寄せ実践（How-to） ─────────────────────────────
_reg(VideoType(
    id    = "howto",
    label = "🌟 引き寄せ実践How-to",
    description = "具体的な手順・テクニックを教える実践系。行動喚起が強い。",

    system_prompt_extra = """
【引き寄せHow-to動画の特別ルール】
- 「今日からできる」「5分でOK」など手軽さを強調
- ステップ形式（「ステップ1:〜します」）で分かりやすく
- 「多くの人が間違えているのは〜」「実は逆効果なのが〜」など反常識的な視点を入れる
- 成功体験談（「〜さんはこの方法で〜しました」）を1〜2個挿入
- ポジティブで行動的なトーン。「やってみましょう！」で締める
""",

    script_structure = """
構成（必ず守ること）:
[フック 1分]   衝撃的な結果 or 多くの人が知らない事実で掴む
[本編 6分]     実践ステップを4〜6つ、具体的に説明
               各ステップに「なぜ効果があるか」の短い理由を添える
[注意点 30秒]  やってはいけないNG行動を1〜2つ
[締め 30秒]    「まずステップ1だけ今日試してみてください」で背中を押す
""",

    tts_voice  = "ja-JP-NanamiNeural",
    tts_rate   = "+5%",   # やや早め・テンポよく
    bg_keywords = [
        "success abundance prosperity",
        "sunrise motivation",
        "nature path forward",
        "golden light breakthrough",
        "lotus bloom water",
    ],
    subtitle_style = SubtitleStyle(
        fontsize       = 52,
        primary_colour = "&H00FFFFFF",
        outline_colour = "&H00000000",
        bold           = -1,
        outline        = 3.0,
        margin_v       = 60,
    ),
    title_style = TitleStyle(
        fontsize    = 68,
        fontcolor   = "white",
        bordercolor = "black",
        borderw     = 3,
        y_ratio     = 0.08,
        duration_sec= 5.0,
        box         = True,
        boxcolor    = "black@0.5",
    ),
    default_duration_min = 7,
))


# ── 5. 癒し・瞑想誘導 ────────────────────────────────────
_reg(VideoType(
    id    = "healing",
    label = "🌙 癒し・瞑想誘導",
    description = "リラクゼーション・瞑想・睡眠導入向け。ゆったりした誘導音声。",

    system_prompt_extra = """
【癒し・瞑想誘導動画の特別ルール】
- 非常にゆっくり、穏やかな誘導口調（催眠誘導に近い）
- 「息をゆっくり吸ってください」「体の力を抜いてください」など体感覚への語りかけ
- 自然・宇宙・光のイメージを多用（「温かい金色の光が〜」）
- ネガティブな言葉を一切使わない
- 沈黙（間）を想定した文章構成（「…少し間を置いて…」と書かない、自然に間が生まれる長さ）
""",

    script_structure = """
構成（必ず守ること）:
[導入 2分]   深呼吸の誘導 → 体のリラックス → 心を静める準備
[瞑想本編 6分] テーマに沿ったビジュアライゼーション or ヒーリングの誘導
              光・色・感覚を具体的にイメージさせる描写
[覚醒 1分]   ゆっくり意識を戻す誘導 → 「今のあなたはすでに癒されています」
""",

    tts_voice  = "ja-JP-NanamiNeural",
    tts_rate   = "-20%",   # 最もゆっくり
    bg_keywords = [
        "calm water reflection",
        "forest morning mist",
        "aurora borealis night",
        "underwater serene blue",
        "moonlight peaceful nature",
    ],
    subtitle_style = SubtitleStyle(
        fontsize       = 48,
        primary_colour = "&H00DDEEFF",   # 淡い青白
        outline_colour = "&H00223344",
        bold           = 0,
        outline        = 2.0,
        shadow         = 2.0,
        margin_v       = 90,
        alignment      = 2,
    ),
    title_style = TitleStyle(
        fontsize    = 66,
        fontcolor   = "#DDEEFF",
        bordercolor = "#223344",
        borderw     = 2,
        y_ratio     = 0.12,
        duration_sec= 7.0,
    ),
    default_duration_min = 10,
))


# ── 6. スピ雑学・不思議話 ────────────────────────────────
_reg(VideoType(
    id    = "trivia",
    label = "🔮 スピ雑学・不思議話",
    description = "「知らないと損する」「衝撃の真実」系。エンタメ寄り。拡散されやすい。",

    system_prompt_extra = """
【スピ雑学動画の特別ルール】
- 「実は〜だった」「99%の人が知らない〜」「衝撃の事実」で始める
- テンポよくサクサク進む（1トピック30〜60秒）
- ランキング形式（「第5位〜、第1位〜」）も効果的
- 「コメントで教えてください」「あなたはどう思いますか？」で視聴者参加を促す
- 少し怖い話・不思議な話も交えてOK（過激すぎない範囲で）
""",

    script_structure = """
構成（必ず守ること）:
[つかみ 30秒] 「今日はあなたが知らないはずの〜を紹介します」
[本編 7分]    5〜8個のスピ雑学 or ランキングをテンポよく紹介
              各トピックの最後に「あなたはこれを経験したことがありますか？」
[締め 30秒]   「他にも不思議な体験がある方はコメントへ」+ 次回予告
""",

    tts_voice  = "ja-JP-NanamiNeural",
    tts_rate   = "+8%",   # テンポよく
    bg_keywords = [
        "mystical dark forest",
        "ancient ruins mysterious",
        "cosmos galaxy dark",
        "pyramid sacred geometry",
        "moon night mysterious",
    ],
    subtitle_style = SubtitleStyle(
        fontsize       = 52,
        primary_colour = "&H00FFFFFF",
        outline_colour = "&H00000000",
        bold           = -1,
        outline        = 3.0,
        margin_v       = 55,
    ),
    title_style = TitleStyle(
        fontsize    = 70,
        fontcolor   = "white",
        bordercolor = "black",
        borderw     = 3,
        y_ratio     = 0.08,
        duration_sec= 5.0,
        box         = True,
        boxcolor    = "black@0.6",
    ),
    default_duration_min = 8,
))


# ════════════════════════════════════════════════════════
# ユーティリティ
# ════════════════════════════════════════════════════════

def get_type(type_id: str) -> VideoType:
    """IDからVideoTypeを取得。不明なIDはデフォルト(education)を返す"""
    if type_id not in TYPES:
        print(f"[VideoType] 不明なtype_id '{type_id}' → 'education' を使用")
        return TYPES["education"]
    return TYPES[type_id]


def list_types() -> None:
    """利用可能な型の一覧を表示"""
    print("\n利用可能な動画の型:")
    print("-" * 55)
    for vt in TYPES.values():
        print(f"  {vt.label:<25} --type {vt.id}")
        print(f"    {vt.description}")
    print("-" * 55)


if __name__ == "__main__":
    list_types()
