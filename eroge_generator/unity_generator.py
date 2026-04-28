"""
unity_generator.py
Gemini APIを使ってUnity向けゲームデザインとC#スクリプトを生成する
"""

import json
import re
import time
import queue as _q
import threading as _th


# ─────────────────────────────────────────────
#  低レベルAPI呼び出しユーティリティ
# ─────────────────────────────────────────────

def _parse_retry_after(error_str: str) -> int:
    m = re.search(r'retry_delay\s*\{[^}]*seconds:\s*(\d+)', str(error_str), re.DOTALL)
    return int(m.group(1)) + 3 if m else 0


def _stream(model, prompt, system="", log=print) -> str:
    full = f"{system}\n\n{prompt}" if system else prompt
    max_attempts = 5
    _WALL_TIMEOUT = 120
    for attempt in range(max_attempts):
        try:
            chunk_q = _q.Queue()

            def _api_worker(fp=full, cq=chunk_q):
                try:
                    for chunk in model.generate_content(fp, stream=True,
                                                        request_options={"timeout": _WALL_TIMEOUT}):
                        cq.put(('chunk', chunk.text or ""))
                except Exception as exc:
                    cq.put(('error', exc))
                finally:
                    cq.put(('done', None))

            _th.Thread(target=_api_worker, daemon=True).start()

            result = []
            chars = 0
            dot_next = 200
            deadline = time.time() + _WALL_TIMEOUT
            log(f"  Gemini API 呼び出し中{'（リトライ ' + str(attempt) + '回目）' if attempt > 0 else ''}...")

            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError(f"Gemini API が{_WALL_TIMEOUT}秒応答なし")
                try:
                    kind, val = chunk_q.get(timeout=min(remaining, 2.0))
                except _q.Empty:
                    continue
                if kind == 'chunk':
                    result.append(val)
                    chars += len(val)
                    if chars >= dot_next:
                        log(f"  受信中... {chars}字")
                        dot_next += 500
                elif kind == 'error':
                    raise val
                elif kind == 'done':
                    break

            log(f"  受信完了 ({chars}字)")
            return _clean("".join(result))
        except Exception as e:
            err = str(e)
            if attempt < max_attempts - 1:
                retry_after = _parse_retry_after(err)
                if retry_after:
                    log(f"  ⚠️ レート制限 — {retry_after}秒後にリトライ... ({attempt+1}/{max_attempts})")
                    time.sleep(retry_after)
                else:
                    wait = 5 + attempt * 5
                    log(f"  API エラー: {err[:80]} → {wait}秒後にリトライ ({attempt+1}/{max_attempts})")
                    time.sleep(wait)
            else:
                raise


def _clean(text):
    text = re.sub(r"```[a-z]*\n?", "", text)
    return re.sub(r"```", "", text).strip()


def _parse_json_with_retry(model, prompt, system="", max_retry=3, log=print) -> dict:
    for attempt in range(max_retry):
        raw = _stream(model, prompt, system, log)
        m = re.search(r'\{[\s\S]+\}', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError as e:
                log(f"  JSON error (try {attempt+1}/{max_retry}): {e}")
        else:
            log(f"  JSON not found (try {attempt+1}/{max_retry})")
        if attempt < max_retry - 1:
            time.sleep(2)
    raise ValueError(f"JSON生成に{max_retry}回失敗")


# ─────────────────────────────────────────────
#  ゲームデザイン生成
# ─────────────────────────────────────────────

def generate_game_concept(model, genre: str, game_type: str, log=print) -> dict:
    system = (
        "あなたはゲームデザイナーです。Unity向けR18エロゲのコンセプトを"
        "JSON形式で生成してください。必ず有効なJSONのみを返してください。"
    )
    prompt = f"""{genre}ジャンルの{game_type}のコンセプトを以下のJSON形式で生成してください。
必ず有効なJSONのみを返し、説明文は不要です。

{{
  "title": "ゲームタイトル（日本語）",
  "genre_desc": "ジャンル説明（30字以内）",
  "story": "あらすじ（100字以内）",
  "setting": "舞台設定（30字以内）",
  "protagonist": {{
    "name": "主人公名（日本語）",
    "description": "説明（40字以内）"
  }},
  "heroines": [
    {{
      "name": "ヒロイン名（日本語）",
      "archetype": "属性（ツンデレ等）",
      "description": "説明（40字以内）",
      "h_scenes": ["シーン名1", "シーン名2"],
      "unlock_condition": "解放条件（30字以内）"
    }}
  ],
  "game_systems": ["システム説明（20字以内）"],
  "scenes": [
    {{
      "name": "シーン名（日本語）",
      "type": "dialogue",
      "description": "説明（40字以内）",
      "background": "背景の説明（20字以内）"
    }}
  ],
  "h_system": "Hシーンの発生条件・システム説明（50字以内）",
  "monetization": "DLSiteでの販売戦略（30字以内）"
}}

条件:
- heroinesは2〜4人
- scenesは5〜8シーン（typeはdialogue/choice/h_scene のいずれか）
- game_systemsは3〜5個
- JSONのキーはすべて英語（値の日本語はOK）
- R18エロゲとして魅力的な設定にすること
"""
    return _parse_json_with_retry(model, prompt, system, log=log)


# ─────────────────────────────────────────────
#  C#スクリプト生成
# ─────────────────────────────────────────────

def generate_game_manager(model, concept: dict, log=print) -> str:
    system = (
        "あなたはUnity専門のゲームプログラマーです。"
        "有効なC# Unityスクリプトのみを返してください。コードブロック(```)は不要です。"
    )
    heroines = [h.get("name", "") for h in concept.get("heroines", [])]
    prompt = f"""
以下の仕様でUnity用GameManager.csを生成してください。

ゲーム情報:
- タイトル: {concept.get('title', 'ゲーム')}
- ヒロイン: {heroines}

要件:
- public class GameManager : MonoBehaviour（Singletonパターン）
- public static GameManager Instance;
- int currentChapter, totalScore
- bool isGameOver, isCleared
- Dictionary<string, int> heroineAffection（各ヒロインの好感度管理、初期値0）
- void AddAffection(string heroineName, int amount)
- void NextScene()
- void GameOver()
- void GameClear()
- void SaveGame() / void LoadGame()（PlayerPrefs使用）
- event Action<string,int> OnAffectionChanged
- event Action OnGameClear
- DontDestroyOnLoad(gameObject)
- Awake でSingleton初期化 & LoadGame()

コードのみ返してください。説明不要。
"""
    return _stream(model, prompt, system, log)


def generate_dialogue_system(model, concept: dict, log=print) -> str:
    system = (
        "あなたはUnity専門のゲームプログラマーです。"
        "有効なC# Unityスクリプトのみを返してください。コードブロック(```)は不要です。"
    )
    prompt = f"""
以下の仕様でUnity用DialogueSystem.csを生成してください。

ゲーム情報:
- タイトル: {concept.get('title', 'ゲーム')}

要件:
- using TMPro; using UnityEngine.UI; を使う
- public class DialogueSystem : MonoBehaviour
- [System.Serializable] class DialogueLine {{ public string character; public string text; public string emotion; public string background; }}
- [System.Serializable] class DialogueScene {{ public string sceneName; public DialogueLine[] lines; public string[] choices; }}
- TextMeshProUGUI nameText, dialogueText（インスペクターで設定）
- Image backgroundImage, characterImage（インスペクターで設定）
- GameObject dialoguePanel, choicePanel
- Button[] choiceButtons
- void LoadDialogueData(string jsonPath)（StreamingAssetsからJSON読込）
- void StartScene(string sceneName)
- void NextLine()
- void ShowChoices(string[] choices, System.Action<int> callback)
- IEnumerator TypeText(string text)（タイプライター効果）
- Update()でSpaceキー/クリックでNextLine()
- GameManagerと連携

コードのみ返してください。説明不要。
"""
    return _stream(model, prompt, system, log)


def generate_character_controller(model, concept: dict, heroine: dict, log=print) -> str:
    system = (
        "あなたはUnity専門のゲームプログラマーです。"
        "有効なC# Unityスクリプトのみを返してください。コードブロック(```)は不要です。"
    )
    safe_name = re.sub(r'[^\w]', '', heroine.get('name', 'Heroine'))
    prompt = f"""
以下の仕様でUnity用キャラクターコントローラースクリプトを生成してください。

キャラクター:
- 名前: {heroine.get('name', 'ヒロイン')}
- 属性: {heroine.get('archetype', 'ツンデレ')}
- Hシーン: {heroine.get('h_scenes', [])}
- 解放条件: {heroine.get('unlock_condition', '好感度100以上')}

要件:
- public class {safe_name}Controller : MonoBehaviour
- [SerializeField] Sprite[] normalSprites, happySprites, shySprites, angrySprites, lewdSprites
- SpriteRenderer spriteRenderer
- enum Emotion {{ Normal, Happy, Shy, Angry, Lewd }}
- Emotion currentEmotion
- void SetEmotion(Emotion emotion)（スプライト切り替え）
- void OnAffectionChanged(string name, int value)（GameManagerのイベントを購読）
- void TriggerHScene()（好感度条件達成時に呼ばれる）
- bool IsUnlocked()（好感度条件チェック）
- Start()でGameManager.Instance.OnAffectionChangedを購読

コードのみ返してください。説明不要。
"""
    return _stream(model, prompt, system, log)


def generate_ui_manager(model, concept: dict, log=print) -> str:
    system = (
        "あなたはUnity専門のゲームプログラマーです。"
        "有効なC# Unityスクリプトのみを返してください。コードブロック(```)は不要です。"
    )
    heroines = [h.get("name", "") for h in concept.get("heroines", [])]
    prompt = f"""
以下の仕様でUnity用UIManager.csを生成してください。

ゲーム情報:
- タイトル: {concept.get('title', 'ゲーム')}
- ヒロイン: {heroines}

要件:
- using TMPro; using UnityEngine.UI;
- public class UIManager : MonoBehaviour（Singletonパターン）
- [SerializeField] GameObject titleScreen, gameScreen, hSceneScreen, galleryScreen, gameOverScreen, clearScreen
- [SerializeField] TextMeshProUGUI affectionText, chapterText, titleText
- void ShowScreen(GameObject screen)（全画面非表示→指定のみ表示）
- void ShowTitleScreen() / void ShowGameScreen() / void ShowGameOver() / void ShowClear()
- void ShowHScene(string sceneName)
- void UpdateAffectionUI(string heroineName, int value)
- IEnumerator FadeIn(CanvasGroup cg) / FadeOut(CanvasGroup cg)（0.5秒）
- Start()でGameManagerのイベント購読
- OnStartButton(), OnGalleryButton(), OnExitButton()（Buttonから呼ぶ）

コードのみ返してください。説明不要。
"""
    return _stream(model, prompt, system, log)


def generate_h_scene_manager(model, concept: dict, log=print) -> str:
    system = (
        "あなたはUnity専門のゲームプログラマーです。"
        "有効なC# Unityスクリプトのみを返してください。コードブロック(```)は不要です。"
    )
    all_h_scenes = []
    for h in concept.get("heroines", []):
        all_h_scenes.extend(h.get("h_scenes", []))
    prompt = f"""
以下の仕様でUnity用HSceneManager.csを生成してください。

Hシーン一覧: {all_h_scenes}

要件:
- using UnityEngine.UI; using TMPro;
- public class HSceneManager : MonoBehaviour（Singletonパターン）
- Dictionary<string, bool> unlockedScenes
- [SerializeField] Image sceneImage
- [SerializeField] TextMeshProUGUI sceneNameText
- [SerializeField] GameObject hScenePanel, galleryPanel
- Sprite[] currentSprites
- int currentIndex
- bool isAutoPlay
- float autoPlayInterval = 2.5f
- Coroutine autoPlayCoroutine
- void PlayScene(string sceneName)（Resourcesからスプライト読み込み）
- void NextSprite() / void PrevSprite()
- void ToggleAutoPlay()
- IEnumerator AutoPlayRoutine()
- void UnlockScene(string sceneName)（PlayerPrefsに保存）
- bool IsUnlocked(string sceneName)
- void OpenGallery()（解放済みシーン一覧表示）
- void CloseHScene()

コードのみ返してください。説明不要。
"""
    return _stream(model, prompt, system, log)


def generate_editor_setup(model, concept: dict, log=print) -> str:
    system = (
        "あなたはUnity専門のゲームプログラマーです。"
        "有効なC# Unity Editorスクリプトのみを返してください。コードブロック(```)は不要です。"
    )
    title = concept.get("title", "Game")
    heroines = [h.get("name", "") for h in concept.get("heroines", [])]
    scenes_list = [s.get("name", "") for s in concept.get("scenes", [])]
    prompt = f"""
以下の仕様でUnity Editor拡張スクリプト（Assets/Scripts/Editor/GameSetup.cs）を生成してください。
このスクリプトはUnityエディターのメニューから実行し、ゲームシーンを自動セットアップします。

ゲーム情報:
- タイトル: {title}
- ヒロイン: {heroines}
- シーン: {scenes_list}

要件:
- using UnityEditor; using UnityEngine; using UnityEngine.UI; using TMPro;
- public class GameSetup : Editor
- [MenuItem("Tools/{title}/完全セットアップ")] static void SetupGame()
  実行内容:
  1. Main Camera: orthographic = true, size = 5, Clear Flags = Solid Color
  2. Canvas (Screen Space Overlay) 作成 + CanvasScaler(1280x720 reference)
  3. EventSystem 作成
  4. Background (Image, stretch to full) 作成
  5. CharacterImage (Image, 中央配置) 作成
  6. DialoguePanel (Panel, 下部) 作成
     - NameText (TextMeshProUGUI)
     - DialogueText (TextMeshProUGUI)
     - NextIndicator (Image/Text)
  7. GameManager, DialogueSystem, UIManager, HSceneManager 各空GameObjectにAddComponent
  8. EditorUtility.DisplayDialog("セットアップ完了", "シーン構造を作成しました。\\nSprite・Audioを追加してください。", "OK")

- [MenuItem("Tools/{title}/使い方を開く")] static void OpenReadme()
  → Application.OpenURL or EditorUtility.RevealInFinder(Application.dataPath + "/../README.md")

コードのみ返してください。説明不要。
"""
    return _stream(model, prompt, system, log)


def generate_dialogue_data(model, concept: dict, log=print) -> str:
    system = (
        "あなたはR18エロゲシナリオライターです。"
        "有効なJSONのみを返してください。コードブロック(```)は不要です。"
    )
    heroines = concept.get("heroines", [])
    scenes = concept.get("scenes", [])
    heroine_names = [h.get("name") for h in heroines]
    scene_names = [s.get("name") for s in scenes]

    prompt = f"""
以下のゲーム情報に基づいてダイアログデータをJSON形式で生成してください。

ゲーム情報:
- タイトル: {concept.get('title', 'ゲーム')}
- あらすじ: {concept.get('story', '')}
- 主人公: {concept.get('protagonist', {}).get('name', '主人公')}
- ヒロイン: {heroine_names}
- シーン: {scene_names}
- Hシステム: {concept.get('h_system', '')}

以下のJSON形式で全シーンのセリフを生成してください:
{{
  "scenes": [
    {{
      "sceneName": "シーン名",
      "lines": [
        {{
          "character": "キャラクター名",
          "text": "セリフ（自然な日本語）",
          "emotion": "Normal",
          "background": "背景名"
        }}
      ],
      "choices": []
    }}
  ]
}}

条件:
- 全シーン（{scene_names}）をすべて含める
- 各シーン5〜10行のセリフ
- emotionはNormal/Happy/Shy/Angry/Lewdのいずれか
- choicesがある場合は["選択肢1", "選択肢2"]形式
- R18エロゲらしいセリフを自然に含める
- JSONのみ返す（説明不要）
"""
    return _stream(model, prompt, system, log)
