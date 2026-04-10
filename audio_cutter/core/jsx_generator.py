"""
jsx_generator.py
Premiere Pro ExtendScript（JSX）の生成
"""
import json
from typing import List, Dict


def generate_jsx(cuts: List[Dict], output_path: str, preview_only: bool = False) -> str:
    """
    カットリストからPremiere Pro用JSXを生成する。

    カットは末尾から順に処理することで、リップル削除後のタイムシフトを回避する。

    Args:
        cuts:         [{"start": float, "end": float, "reason": str}]
        output_path:  出力JSXファイルパス
        preview_only: Trueの場合マーカー追加のみ（カットしない）

    Returns:
        output_path
    """
    # 末尾から処理するため逆順ソート
    sorted_cuts = sorted(cuts, key=lambda x: x["start"], reverse=True)
    cuts_js = json.dumps(sorted_cuts, ensure_ascii=False, indent=2)

    total_sec = sum(c["end"] - c["start"] for c in cuts)
    silence_count = sum(1 for c in cuts if c["reason"].startswith("silence"))
    filler_count = sum(1 for c in cuts if c["reason"].startswith("filler"))
    stammer_count = sum(1 for c in cuts if "stammer" in c["reason"] or "re-take" in c["reason"])

    script = f"""// ============================================================
// Audio Auto Cutter - Premiere Pro ExtendScript
// 使い方: Premiere Pro > ファイル > スクリプト > スクリプトを実行
// シーケンスを開いた状態で実行してください
// ============================================================
// カット数: {len(cuts)} 箇所
//   無音/ノイズ: {silence_count} 箇所
//   フィラー:   {filler_count} 箇所
//   噛み:       {stammer_count} 箇所
//   カット合計: {total_sec:.1f} 秒
// ============================================================

var CUTS = {cuts_js};

// true = マーカー追加のみ（確認用）、false = リップル削除を実行
var PREVIEW_ONLY = {'true' if preview_only else 'false'};

// ---- ユーティリティ ----

function log(msg) {{
    $.writeln("[AudioCutter] " + msg);
}}

function tryRippleDelete() {{
    // 言語によってメニュー名が異なるため複数試行
    var names = ["Ripple Delete", "リップル削除", "연속 삭제", "Ripple-Löschen"];
    for (var i = 0; i < names.length; i++) {{
        var id = app.findMenuItemID(names[i]);
        if (id > 0) {{
            app.executeCommand(id);
            return true;
        }}
    }}
    // フォールバック: 既知のコマンドID
    var fallbackIds = [2233, 61876, 5];
    for (var j = 0; j < fallbackIds.length; j++) {{
        try {{
            app.executeCommand(fallbackIds[j]);
            return true;
        }} catch(e) {{}}
    }}
    return false;
}}

// ---- プレビューモード（マーカー追加） ----

function addMarkers(seq) {{
    // 逆順のCUTSを元の順序に戻す
    var ordered = CUTS.slice().reverse();
    for (var i = 0; i < ordered.length; i++) {{
        var cut = ordered[i];
        try {{
            var m = seq.markers.createMarker(cut.start);
            m.end = cut.end;
            m.name = cut.reason;
            m.type = 2; // range marker
        }} catch(e) {{
            log("マーカー追加失敗: " + e.message);
        }}
    }}
    alert(
        "マーカーを " + ordered.length + " 箇所追加しました。\\n\\n" +
        "タイムライン上でカット位置を確認し、\\n" +
        "問題なければ PREVIEW_ONLY = false にして再実行してください。"
    );
}}

// ---- 実行モード（リップル削除） ----

function runCuts(seq) {{
    var ok = 0, ng = 0, skipped = 0;

    for (var i = 0; i < CUTS.length; i++) {{
        var cut = CUTS[i];
        var duration = cut.end - cut.start;

        if (duration < 0.05) {{
            skipped++;
            continue;
        }}

        log("["+(i+1)+"/"+CUTS.length+"] " + cut.start.toFixed(3)+"s ~ "+cut.end.toFixed(3)+"s  "+cut.reason);

        try {{
            var inPt = new Time();
            inPt.seconds = cut.start;
            var outPt = new Time();
            outPt.seconds = cut.end;

            seq.setInPoint(inPt.ticks);
            seq.setOutPoint(outPt.ticks);

            if (!tryRippleDelete()) {{
                log("  リップル削除コマンドが見つかりません（手動で実行してください）");
                ng++;
                continue;
            }}
            ok++;
        }} catch(e) {{
            log("  エラー: " + e.message);
            ng++;
        }}
    }}

    alert(
        "音声カット完了！\\n\\n" +
        "成功: " + ok + " 箇所\\n" +
        "失敗: " + ng + " 箇所\\n" +
        "スキップ: " + skipped + " 箇所\\n\\n" +
        "Ctrl+Z で元に戻せます"
    );
}}

// ---- エントリーポイント ----

function main() {{
    var project = app.project;
    if (!project) {{ alert("プロジェクトが開かれていません"); return; }}

    var seq = project.activeSequence;
    if (!seq) {{ alert("アクティブなシーケンスがありません\\nシーケンスをダブルクリックで開いてから実行してください"); return; }}

    if (CUTS.length === 0) {{ alert("カット箇所がありません"); return; }}

    var modeStr = PREVIEW_ONLY
        ? "プレビュー（マーカー追加のみ、カットしない）"
        : "実行（リップル削除）";

    var totalSec = 0;
    for (var i = 0; i < CUTS.length; i++) {{ totalSec += CUTS[i].end - CUTS[i].start; }}

    var msg =
        "【Audio Auto Cutter】\\n\\n" +
        "カット数: " + CUTS.length + " 箇所\\n" +
        "カット合計: " + totalSec.toFixed(1) + " 秒\\n" +
        "モード: " + modeStr + "\\n\\n" +
        "シーケンス: " + seq.name + "\\n\\n" +
        "実行しますか？";

    if (!confirm(msg)) return;

    if (PREVIEW_ONLY) {{
        addMarkers(seq);
    }} else {{
        runCuts(seq);
    }}
}}

main();
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script)

    return output_path
