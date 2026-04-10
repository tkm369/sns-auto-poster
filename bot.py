"""
友達模倣 Discord Bot（完全無料版）
===================================
【使い方】
1. FRIEND_NAME と FRIEND_MESSAGES を友達のものに書き換える
2. .env ファイルを作って DISCORD_TOKEN と GROQ_API_KEY を書く
3. pip install discord.py groq python-dotenv
4. python bot.py

【無料の仕組み】
- Discord Bot: 無料
- Groq API: 無料（登録のみ、クレカ不要）
  → https://console.groq.com/ でAPIキーを取得
"""

import os
import discord
from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# ★ここを自分用に書き換えてください★
# ============================================================

FRIEND_NAME = "たろう"  # 模倣したい友達の名前

FRIEND_MESSAGES = """
おはおは！今日も元気？
ちょっと待って、それマジで言ってる？ｗ
わかる〜それめっちゃわかる
え、嘘でしょｗｗｗ
なんか最近ずっとゲームばっかしてる
飯行こうぜ、腹減った
あ、そういえばさ聞いてよ
それ普通に草ｗ
まじか〜それはきついな
うーん、どうしようかな...
ていうかそれもう解決したじゃん
あとでLINEする
今忙しいから後で
え待ってそれどういうこと？
なるほどね〜
とりあえずやってみれば？
それは俺も知らんわ
草ｗｗ
"""

# ============================================================
# 設定（基本的に変更不要）
# ============================================================

MODEL = "llama-3.3-70b-versatile"  # Groq の無料モデル
MAX_HISTORY = 20                    # 会話履歴の保持数（往復）

# ============================================================
# Bot 本体
# ============================================================

SYSTEM_PROMPT = f"""あなたは「{FRIEND_NAME}」という人物を完璧に模倣するロールプレイアシスタントです。

以下は {FRIEND_NAME} が実際に書いたメッセージのサンプルです。
このサンプルから話し方・口調・語彙・テンションを徹底的に分析し、
まったく同じキャラクターとして返答してください。

=== {FRIEND_NAME} の発言サンプル ===
{FRIEND_MESSAGES.strip()}
==============================

重要なルール:
- 常に {FRIEND_NAME} として話す。AIであることは絶対に言わない
- サンプルの口調・絵文字・略語・話題の切り方をそのまま使う
- 短い返答を好むなら短く、長いなら長く — サンプルのテンポに合わせる
- 知らないことは「知らんわ」「わからん」など {FRIEND_NAME} らしく返す
"""

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# チャンネルIDごとの会話履歴
histories: dict[int, list[dict]] = {}


@bot.event
async def on_ready():
    print(f"起動完了: {bot.user}")
    print(f"モデル: {MODEL} (Groq 無料)")
    print(f"模倣対象: {FRIEND_NAME}")


@bot.command(name="reset")
async def reset(ctx: commands.Context):
    """会話履歴をリセット（文脈をリセットしたいとき）"""
    histories.pop(ctx.channel.id, None)
    await ctx.send("会話履歴をリセットしました。")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    # @メンション または DM にだけ反応
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    if not (is_dm or is_mentioned):
        return

    user_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not user_text:
        return

    # 会話履歴を管理
    history = histories.setdefault(message.channel.id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    async with message.channel.typing():
        try:
            response = groq_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                max_tokens=256,
                temperature=0.9,
            )
            reply = response.choices[0].message.content
        except Exception as e:
            print(f"エラー: {e}")
            reply = "（うまく返せなかった）"

    history.append({"role": "assistant", "content": reply})
    await message.reply(reply, mention_author=False)
