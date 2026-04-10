import os
import json
from typing import List, Dict


def generate_extendscript(clips: List[Dict], output_path: str) -> str:
    """
    Premiere Pro用のExtendScript (.jsx) を生成する。

    clips の各要素:
        file_path     : ダウンロード済み動画の絶対パス
        file_name     : ファイル名（importした後の検索用）
        start_seconds : タイムライン上の挿入開始位置（秒）
        end_seconds   : タイムライン上の挿入終了位置（秒）
        subtitle_text : 元の字幕テキスト（コメント用）
    """
    clips_js = json.dumps(clips, ensure_ascii=False, indent=2)

    script = f"""// ============================================================
// B-Roll Auto Inserter - Premiere Pro ExtendScript
// 使い方: Premiere Pro で ファイル > スクリプト > スクリプトを実行
// ============================================================

var CLIPS = {clips_js};

// ---- ユーティリティ ----

function log(msg) {{
    $.writeln("[BRoll] " + msg);
}}

function findItemByName(parentItem, name) {{
    for (var i = 0; i < parentItem.children.numItems; i++) {{
        if (parentItem.children[i].name === name) {{
            return parentItem.children[i];
        }}
    }}
    return null;
}}

// ---- メイン ----

function run() {{
    var project = app.project;
    if (!project) {{
        alert("プロジェクトが開かれていません");
        return;
    }}

    var sequence = project.activeSequence;
    if (!sequence) {{
        alert("アクティブなシーケンスがありません。\\nシーケンスを選択してから実行してください。");
        return;
    }}

    // V2トラック（Bロール用）を確認
    if (sequence.videoTracks.numTracks < 2) {{
        alert("V2トラックがありません。\\nシーケンスにV2トラックを追加してから実行してください。");
        return;
    }}
    var brollTrack = sequence.videoTracks[1]; // V2

    var ok = 0;
    var ng = 0;

    for (var i = 0; i < CLIPS.length; i++) {{
        var clip = CLIPS[i];
        var filePath = clip.file_path;
        var fileName = clip.file_name;

        log("処理中 [" + (i + 1) + "/" + CLIPS.length + "]: " + clip.subtitle_text);

        // ① importFiles でプロジェクトに取り込む
        var importPaths = [filePath];
        var result = project.importFiles(importPaths, true, project.rootItem, false);
        if (!result) {{
            log("  インポート失敗: " + filePath);
            ng++;
            continue;
        }}

        // ② プロジェクトパネルから該当アイテムを探す
        var item = findItemByName(project.rootItem, fileName);
        if (!item) {{
            log("  アイテムが見つかりません: " + fileName);
            ng++;
            continue;
        }}

        // ③ 挿入位置を計算
        var startTime = new Time();
        startTime.seconds = clip.start_seconds;

        // ④ トラックに挿入
        brollTrack.insertClip(item, startTime.ticks);

        // ⑤ 末尾のクリップを目的の長さにトリム
        var duration = clip.end_seconds - clip.start_seconds;
        var clips = brollTrack.clips;
        // 直近に挿入されたクリップを特定（開始位置が一致するもの）
        for (var j = 0; j < clips.numItems; j++) {{
            var tc = clips[j];
            var tcStart = new Time();
            tcStart.ticks = tc.start.ticks;
            if (Math.abs(tcStart.seconds - clip.start_seconds) < 0.1) {{
                var newEnd = new Time();
                newEnd.seconds = clip.start_seconds + duration;
                tc.end = newEnd;
                break;
            }}
        }}

        log("  OK: " + fileName);
        ok++;
    }}

    alert("Bロール挿入完了！\\n\\n成功: " + ok + " 件\\n失敗: " + ng + " 件");
}}

run();
""".strip()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script)

    return output_path
