"""
TikTokのセッションIDをCDP経由で取得する。
Chrome を一時起動してデバッグポートからクッキーを読む。
"""
import sys
import subprocess
import time
import json
import urllib.request
import os

PROFILE_DIR = r"C:\tiktok_debug_profile"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT    = 9224  # uploader_workerの9223とかぶらないよう別ポート


def get_session_id():
    # Chrome起動（ヘッドレス相当 + デバッグポート）
    proc = subprocess.Popen(
        [
            CHROME_PATH,
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--headless=new",
            f"--remote-allow-origins=http://127.0.0.1:{CDP_PORT}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # CDP が起動するまで待つ
        for _ in range(20):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2
                ) as r:
                    r.read()
                break
            except Exception:
                continue
        else:
            return None

        # WebSocket URLを取得
        with urllib.request.urlopen(
            f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=5
        ) as r:
            targets = json.loads(r.read())

        if not targets:
            # 新しいタブを開く
            with urllib.request.urlopen(
                f"http://127.0.0.1:{CDP_PORT}/json/new", timeout=5
            ) as r:
                targets = [json.loads(r.read())]

        ws_url = targets[0]["webSocketDebuggerUrl"]

        # WebSocket で CDP コマンドを送る
        import websocket  # websocket-client
        ws = websocket.create_connection(ws_url, timeout=10)

        ws.send(json.dumps({
            "id": 1,
            "method": "Network.getCookies",
            "params": {"urls": ["https://www.tiktok.com", "https://.tiktok.com"]}
        }))

        result = json.loads(ws.recv())
        ws.close()

        cookies = result.get("result", {}).get("cookies", [])
        for c in cookies:
            if c["name"] == "sessionid":
                return c["value"]

        return None
    finally:
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    val = get_session_id()
    if val:
        print(val)
    else:
        print("NOT_FOUND")
        sys.exit(1)
