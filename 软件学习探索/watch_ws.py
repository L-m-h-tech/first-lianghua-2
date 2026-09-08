# -*- coding: utf-8 -*-
"""用 CDP Network 域监听页面 WebSocket 连接（观察 cfwtd 网关握手/消息格式）。"""
import json
import time
import urllib.request
import websocket

PORT = 9225


def find_page_ws():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
        tabs = json.loads(r.read().decode("utf-8", "replace"))
    page = [t for t in tabs if t.get("type") == "page"][0]
    return page["webSocketDebuggerUrl"]


def main():
    ws = websocket.create_connection(find_page_ws(), timeout=30, suppress_origin=True)
    # 启用 Network 域，观察 websocket 事件
    ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
    ws.send(json.dumps({"id": 2, "method": "Network.setCacheDisabled", "params": {"cacheDisabled": True}}))
    print("Network.enable sent; watching WebSocket events 12s...")
    deadline = time.time() + 12
    ws.settimeout(1.0)
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
        except Exception:
            continue
        m = msg.get("method", "")
        if m.startswith("Network.webSocket"):
            print(json.dumps(msg, ensure_ascii=False)[:400])
        elif m == "Network.webSocketFrameSent":
            print("SENT:", msg.get("params", {}).get("response", {}).get("payloadData", "")[:200])
    ws.close()
    print("done")


if __name__ == "__main__":
    main()
