# -*- coding: utf-8 -*-
"""capture_net.py -- 用 playwright 加载页面，捕获所有 XHR/fetch 网络请求，输出 JSON。
用于 SPA（jiaoyikecha layui）与 openvlab market 的 API 端点发现。

用法: python capture_net.py <name> <url> [--wait-ms 8000] [--out FILE]
"""
import argparse
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("url")
    ap.add_argument("--wait-ms", type=int, default=9000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        args.name, "数据", f"{args.name}_network.json")

    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
            locale="zh-CN", viewport={"width": 1600, "height": 900})
        page = ctx.new_page()

        def on_response(resp):
            try:
                if resp.request.resource_type in ("xhr", "fetch"):
                    u = resp.url
                    if any(u.startswith(p) for p in ("data:", "blob:")):
                        return
                    rec = {
                        "url": u,
                        "status": resp.status,
                        "method": resp.request.method,
                        "resource_type": resp.request.resource_type,
                    }
                    try:
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct or "text" in ct or u.endswith((".json", ".php")):
                            body = resp.text()
                            if body:
                                rec["body_preview"] = body[:1200]
                    except Exception:
                        pass
                    records.append(rec)
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"goto warn: {e}")
        time.sleep(args.wait_ms / 1000.0)
        # 额外滚动几次触发懒加载
        for _ in range(3):
            try:
                page.mouse.wheel(0, 1200)
                time.sleep(1.2)
            except Exception:
                pass
        try:
            page.screenshot(path=os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                args.name, "数据", f"{args.name}_shot.png"))
        except Exception as e:
            print("shot warn:", e)
        html = page.content()
        with open(os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                args.name, "HTML归档", f"{args.name}_rendered.html"), "w", encoding="utf-8") as f:
            f.write(html)
        browser.close()

    seen = set()
    uniq = []
    for r in records:
        k = (r["method"], r["url"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"url": args.url, "wait_ms": args.wait_ms, "requests": uniq},
                  f, ensure_ascii=False, indent=1)
    print(f"captured {len(records)} xhr/fetch, unique {len(uniq)}")
    for r in uniq[:60]:
        print(f"  {r['method']} {r['status']} {r['url'][:110]}")
    print("saved:", out)


if __name__ == "__main__":
    main()