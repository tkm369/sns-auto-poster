"""
unity_writer.py
Unityプロジェクトを自動生成するパイプライン
"""

import re
import json
import time
from pathlib import Path
from datetime import datetime

OUTPUT_BASE = Path(__file__).parent / "output"

PACKAGE_MANIFEST = {
    "dependencies": {
        "com.unity.textmeshpro": "3.0.6",
        "com.unity.ugui": "1.0.0",
        "com.unity.modules.audio": "1.0.0",
        "com.unity.modules.imageconversion": "1.0.0",
        "com.unity.modules.ui": "1.0.0",
        "com.unity.modules.unitywebrequest": "1.0.0",
        "com.unity.2d.sprite": "1.0.0",
        "com.unity.feature.2d": "2.0.0"
    }
}


def _check_cancel(cancel_event, pause_event=None, log=print):
    if cancel_event and cancel_event.is_set():
        raise InterruptedError("キャンセルされました")
    if pause_event and pause_event.is_set():
        log("  ⏸️ 一時停止中...")
        while pause_event.is_set():
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("キャンセルされました")
            time.sleep(0.5)


def _safe_name(s: str) -> str:
    return re.sub(r'[^\w]', '', s)


def run_full_pipeline(genre: str, api_key: str, game_type: str = "エロVN（ビジュアルノベル）",
                      log=print, cancel_event=None, pause_event=None) -> Path:
    """Unityプロジェクトを完全生成して出力ディレクトリを返す"""
    import google.generativeai as genai
    from unity_generator import (
        generate_game_concept, generate_game_manager, generate_dialogue_system,
        generate_character_controller, generate_ui_manager,
        generate_h_scene_manager, generate_editor_setup, generate_dialogue_data,
    )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    total_steps = 6

    def step(n, name):
        log(f"■ Step {n}/{total_steps}: {name}")

    def chk():
        _check_cancel(cancel_event, pause_event, log)

    # ─── Step 1: コンセプト生成 ───────────────────────────────────
    step(1, "コンセプト生成")
    log(f"[コンセプト] ゲームコンセプト生成中... (ジャンル: {genre} / タイプ: {game_type})")
    concept = generate_game_concept(model, genre, game_type, log=log)
    title = concept.get("title", "UnityEroge")
    log(f"  タイトル決定: 「{title}」")
    chk()

    # ─── 出力ディレクトリ作成 ─────────────────────────────────────
    safe_title = re.sub(r'[^\w\-_]', '_', title)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_BASE / f"unity_{safe_title}_{ts}"

    dirs = [
        "Assets/Scripts",
        "Assets/Scripts/Editor",
        "Assets/Scenes",
        "Assets/Resources",
        "Assets/Resources/HScenes",
        "Assets/StreamingAssets",
        "Assets/Sprites/Characters",
        "Assets/Sprites/Backgrounds",
        "Assets/Audio/BGM",
        "Assets/Audio/SE",
        "Packages",
        "ProjectSettings",
    ]
    for d in dirs:
        (out_dir / d).mkdir(parents=True, exist_ok=True)

    # concept.json 保存
    (out_dir / "concept.json").write_text(
        json.dumps(concept, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Packages/manifest.json
    (out_dir / "Packages" / "manifest.json").write_text(
        json.dumps(PACKAGE_MANIFEST, indent=2), encoding="utf-8"
    )

    log(f"  出力先: {out_dir}")

    # ─── Step 2: コアスクリプト生成 ───────────────────────────────
    step(2, "コアスクリプト生成")

    scripts = [
        ("GameManager.cs",    lambda: generate_game_manager(model, concept, log=log)),
        ("DialogueSystem.cs", lambda: generate_dialogue_system(model, concept, log=log)),
        ("UIManager.cs",      lambda: generate_ui_manager(model, concept, log=log)),
        ("HSceneManager.cs",  lambda: generate_h_scene_manager(model, concept, log=log)),
    ]
    for fname, gen_fn in scripts:
        log(f"[Scripts] {fname} 生成中...")
        code = gen_fn()
        (out_dir / "Assets" / "Scripts" / fname).write_text(code, encoding="utf-8")
        chk()

    # ─── Step 3: キャラクタースクリプト生成 ──────────────────────
    step(3, "キャラクタースクリプト生成")
    for heroine in concept.get("heroines", []):
        h_name = heroine.get("name", "Heroine")
        sname = _safe_name(h_name)
        log(f"[Scripts] {sname}Controller.cs 生成中...")
        code = generate_character_controller(model, concept, heroine, log=log)
        (out_dir / "Assets" / "Scripts" / f"{sname}Controller.cs").write_text(code, encoding="utf-8")
        chk()

    # ─── Step 4: エディタースクリプト生成 ────────────────────────
    step(4, "エディタースクリプト生成")
    log("[Editor] GameSetup.cs 生成中...")
    setup_code = generate_editor_setup(model, concept, log=log)
    (out_dir / "Assets" / "Scripts" / "Editor" / "GameSetup.cs").write_text(
        setup_code, encoding="utf-8"
    )
    chk()

    # ─── Step 5: ダイアログデータ生成 ────────────────────────────
    step(5, "ダイアログデータ（セリフ）生成")
    log("[Data] dialogue_data.json 生成中...")
    raw = generate_dialogue_data(model, concept, log=log)
    try:
        parsed = json.loads(raw)
        json_text = json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        json_text = raw
    (out_dir / "Assets" / "StreamingAssets" / "dialogue_data.json").write_text(
        json_text, encoding="utf-8"
    )
    chk()

    # ─── Step 6: プロジェクト設定・README ────────────────────────
    step(6, "プロジェクト設定・README作成")

    _write_project_settings(out_dir, title, safe_title)
    _write_readme(out_dir, concept)
    _write_gitignore(out_dir)

    # ファイル数カウント
    file_count = sum(1 for f in out_dir.rglob("*") if f.is_file())

    log(f"\n✅ Unity プロジェクト生成完了！")
    log(f"   タイトル: {title}")
    log(f"   出力先: {out_dir}")
    log(f"   総ファイル数: {file_count}個")
    log(f"\n📋 Unityで開く手順:")
    log(f"   1. Unity Hub → 「プロジェクトを追加」→ 上記フォルダを選択")
    log(f"   2. Unity 2022.3 LTS 以降で開く（無料 Personal版でOK）")
    log(f"   3. Unity Editor上部メニュー: Tools > {title} > 完全セットアップ を実行")
    log(f"   4. シーン・UI・スクリプトが自動接続されます")

    return out_dir


def _write_project_settings(out_dir: Path, title: str, safe_title: str):
    safe_id = re.sub(r'[^\w]', '', safe_title)[:20].lower()
    content = f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 24
  productName: {title}
  companyName: IndieStudio
  iPhoneBundleIdentifier: com.indiegame.{safe_id}
  bundleVersion: 1.0
  defaultScreenWidth: 1280
  defaultScreenHeight: 720
  runInBackground: 0
  fullscreenMode: 1
  m_SupportedAspectRatios:
    16:9: 1
    16:10: 1
  scriptingDefineSymbols:
    1: R18_CONTENT
"""
    (out_dir / "ProjectSettings" / "ProjectSettings.asset").write_text(content, encoding="utf-8")

    # GraphicsSettings.asset（最小限）
    graphics = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!30 &1
GraphicsSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 13
  m_Deferred:
    m_Mode: 1
    m_Shader: {fileID: 69, guid: 0000000000000000f000000000000000, type: 0}
  m_DeferredReflections:
    m_Mode: 1
    m_Shader: {fileID: 74, guid: 0000000000000000f000000000000000, type: 0}
  m_ScreenSpaceShadows:
    m_Mode: 1
    m_Shader: {fileID: 64, guid: 0000000000000000f000000000000000, type: 0}
  m_LegacyDeferred:
    m_Mode: 1
    m_Shader: {fileID: 63, guid: 0000000000000000f000000000000000, type: 0}
  m_DepthNormals:
    m_Mode: 1
    m_Shader: {fileID: 62, guid: 0000000000000000f000000000000000, type: 0}
"""
    (out_dir / "ProjectSettings" / "GraphicsSettings.asset").write_text(graphics, encoding="utf-8")

    # QualitySettings.asset
    quality = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!47 &1
QualitySettings:
  m_ObjectHideFlags: 0
  serializedVersion: 5
  m_CurrentQuality: 5
  m_QualitySettings:
  - serializedVersion: 2
    name: Very High
    pixelLightCount: 4
    shadows: 2
    shadowResolution: 2
    shadowDistance: 150
    blendWeights: 4
    anisotropicTextures: 2
    antiAliasing: 2
    softParticles: 1
    realtimeReflectionProbes: 1
    billboardsFaceCameraPosition: 1
    vSyncCount: 1
    lodBias: 2
    maximumLODLevel: 0
    streamingMipmapsActive: 0
    streamingMipmapsAddAllCameras: 1
    streamingMipmapsMemoryBudget: 512
    streamingMipmapsMaxLevelReduction: 2
    streamingMipmapsMaxFileIORequests: 1024
    particleRaycastBudget: 4096
    asyncUploadTimeSlice: 2
    asyncUploadBufferSize: 16
    asyncUploadPersistentBuffer: 1
    resolutionScalingFixedDPIFactor: 1
    customRenderPipeline: {fileID: 0}
    excludedTargetPlatforms: []
"""
    (out_dir / "ProjectSettings" / "QualitySettings.asset").write_text(quality, encoding="utf-8")


def _write_readme(out_dir: Path, concept: dict):
    title = concept.get("title", "ゲーム")
    heroines = concept.get("heroines", [])
    story = concept.get("story", "")
    genre_desc = concept.get("genre_desc", "")
    setting = concept.get("setting", "")
    h_system = concept.get("h_system", "")
    monetization = concept.get("monetization", "")
    game_systems = concept.get("game_systems", [])
    scenes = concept.get("scenes", [])

    heroine_lines = "\n".join(
        f"- **{h.get('name')}** ({h.get('archetype')}) — {h.get('description')}"
        for h in heroines
    )
    system_lines = "\n".join(f"- {s}" for s in game_systems)
    scene_lines = "\n".join(
        f"- [{s.get('type', '?')}] **{s.get('name')}** — {s.get('description', '')}"
        for s in scenes
    )
    h_scene_lines = "\n".join(
        f"- `Assets/Resources/HScenes/{h.get('name')}/` に `scene_0.png`, `scene_1.png` ... を配置"
        for h in heroines
    )

    readme = f"""# {title}

## 概要
{story}

**ジャンル**: {genre_desc}
**舞台**: {setting}
**Hシステム**: {h_system}

---

## ヒロイン
{heroine_lines}

## ゲームシステム
{system_lines}

## シーン構成
{scene_lines}

---

## Unityで開く手順

### 必要なもの
- **Unity Hub**（無料）
- **Unity 2022.3 LTS 以降**（Unity Personal = 無料、年収200万ドル未満）

### セットアップ手順

1. **Unity Hub** を起動 → 「プロジェクトを追加」→ このフォルダを選択
2. Unity で開くと TextMeshPro が自動インストールされます
3. 上部メニュー: **Tools > {title} > 完全セットアップ** を実行
4. ダイアログが出たら「OK」→ シーン・UI・スクリプトが自動構築されます
5. `Assets/Sprites/Characters/` にキャラスプライトを追加
6. `Assets/Audio/BGM/` に BGM を追加して完成

### プロジェクト構造
```
Assets/
├── Scripts/
│   ├── GameManager.cs        # ゲーム管理・好感度システム
│   ├── DialogueSystem.cs     # セリフ・選択肢システム
│   ├── UIManager.cs          # 画面遷移・UI更新
│   ├── HSceneManager.cs      # Hシーン再生・ギャラリー
│   ├── *Controller.cs        # 各ヒロインのコントローラー
│   └── Editor/
│       └── GameSetup.cs      # ★ セットアップメニュー
├── StreamingAssets/
│   └── dialogue_data.json    # セリフデータ（直接編集OK）
├── Sprites/
│   ├── Characters/           # キャラスプライトをここに追加
│   └── Backgrounds/          # 背景画像をここに追加
├── Audio/
│   ├── BGM/                  # BGMをここに追加
│   └── SE/                   # SEをここに追加
└── Resources/
    └── HScenes/              # Hシーン画像をここに追加
        {h_scene_lines.replace(chr(10), chr(10) + '        ')}
```

---

## DLSite販売について
{monetization}

- **Unity Personal**はDLSite販売に使用OK（年収200万ドル未満）
- 「Made with Unity」スプライン画面が入るが、エロゲには問題なし
- Windows向けにビルド: **File > Build Settings > PC, Mac & Linux Standalone**

---

## セリフの編集
`Assets/StreamingAssets/dialogue_data.json` を直接編集することでセリフを変更できます。

---

*このプロジェクトはAI（Gemini + Claude）により自動生成されました。*
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def _write_gitignore(out_dir: Path):
    content = """# Unity
/[Ll]ibrary/
/[Tt]emp/
/[Oo]bj/
/[Bb]uild/
/[Bb]uilds/
/[Ll]ogs/
/[Uu]ser[Ss]ettings/
*.pidb.meta
*.pdb.meta
*.mdb.meta
sysinfo.txt
*.pidb
*.unityproj
*.suo
*.tmp
*.user
*.userprefs
*.booproj
*.svd
*.pdb
*.opendb
*.VC.db
/Assets/AssetStoreTools*
/UserSettings/
"""
    (out_dir / ".gitignore").write_text(content, encoding="utf-8")
