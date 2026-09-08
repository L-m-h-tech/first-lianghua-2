# -*- coding: utf-8 -*-
"""capture_routes.py -- 对同一 SPA 的多个 hash 路由依次导航并捕获网络请求（xhr/fetch）。

用法: python capture_routes.py <name> <base-url> route1 route2 ...
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

G_CUR = {"route": "__home__"}
G_RECS = []


def on_response(resp):
    try:
        if resp.request.resource_type not in ("xhr", "fetch"):
            return
        u = resp.url
        if u.startswith(("data:", "blob:")):
            return
        rec = {"url": u, "status": resp.status, "method": resp.request.method,
               "route": G_CUR["route"]}
        try:
            ct = resp.headers.get("content-type", "")
            if "json" in ct or "text" in ct or u.endswith((".json", ".php")):
                body = resp.text()
                if body and len(body) < 200000:
                    rec["body_preview"] = body[:600]
        except Exception:
            pass
        G_RECS.append(rec)
    except Exception:
        pass


def main():
    name = sys.argv[1]
    base = sys.argv[2]
    routes = sys.argv[3:]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, name, "数据")
    os.makedirs(out_dir, exist_ok=True)

    def route_url(r):
        return f"{base.rstrip('/')}#/{r.lstrip('/')}" if not r.startswith("http") else r

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
            locale="zh-CN", viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        page.on("response", on_response)
        try:
            page.goto(base, wait_until="domcontentloaded", timeout=45000)
            time.sleep(7)
        except Exception as e:
            print("home warn:", e)

        pages_shots = []
        for r in routes:
            G_CUR["route"] = r
            try:
                page.goto(route_url(r), wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"  [{r}] goto warn: {e}")
            time.sleep(7)
            for _ in range(3):
                try:
                    page.mouse.wheel(0, 1500)
                    time.sleep(1.0)
                except Exception:
                    pass
            try:
                fname = name + "_route_" + r.replace("/", "_") + ".png"
                page.screenshot(path=os.path.join(out_dir, fname), full_page=False)
                pages_shots.append(fname)
            except Exception:
                pass
            print(f"[{r}] total so far {len(G_RECS)}")

        browser.close()

    # 按 guess-route 分组
    by_route = {}
    for rec in G_RECS:
        by_route.setdefault(rec["route"], []).append(rec)
    for k in by_route:
        seen = set()
        by_route[k] = [x for x in by_route[k]
                       if not ((x["method"], x["url"]) in seen or seen.add((x["method"], x["url"])))]
    path = os.path.join(out_dir, f"{name}_routes_network.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"base": base, "routes": routes, "screenshots": pages_shots,
                   "by_route": by_route}, f, ensure_ascii=False, indent=1)
    print("saved:", path, "| shots:", pages_shots)


if __name__ == "__main__":
    main()