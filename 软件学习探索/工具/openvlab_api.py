# -*- coding: utf-8 -*-
"""openvlab.cn 匿名 REST API 数据抓取（学习验证用）。

实测三端点均匿名可用（不需要登录/不需要操作 Legend 界面）：
  1. /api/ctamap-all               -> 76 品种全期权波动率地图
  2. /api/dto/{code}               -> 单标的行情（最新/买卖/量仓 + 多周期收益率）
  3. /api/volatility-surface/{code}-> 按月波动率曲面（含希腊字母/持仓/PDF）

用法:
  python openvlab_api.py fetch-all [outdir]   # 抓 ctamap-all + 全品种 dto + 曲面存档
  python openvlab_api.py surface SA [outdir]  # 只抓某一品种曲面
  python openvlab_api.py dto SA               # 打印单标的行情摘要

注意：数据仅用于个人研究；控制请求频率（默认 0.3s 间隔）。
"""
import json
import os
import sys
import time
import urllib.request

BASE = "https://www.openvlab.cn"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_调研资料", "openvlab_api_存档")
os.makedirs(OUT, exist_ok=True)
SLEEP = 0.3


def get(path):
    url = BASE + path
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_ctamap():
    d = get("/api/ctamap-all")
    if d.get("code") != 0:
        print("ctamap-all 失败:", d.get("message"))
        return []
    rows = d.get("result") or []
    with open(os.path.join(OUT, "ctamap_all.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("ctamap-all: %d 品种 -> ctamap_all.json" % len(rows))
    return rows


def fetch_dto(code):
    d = get("/api/dto/" + code)
    if d.get("code") != 0:
        print("dto/%s 失败: %s" % (code, d.get("message")))
        return None
    return d.get("result")


def fetch_surface(code):
    d = get("/api/volatility-surface/" + code)
    if d.get("code") != 0:
        print("surface/%s 失败: %s" % (code, d.get("message")))
        return None
    return d.get("result")


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd = argv[0]
    if cmd == "fetch-all":
        rows = fetch_ctamap()
        # 抓前 N 个品种的 dto+曲面存档（控制流量）
        codes = sorted({r.get("prodUnd") for r in rows if r.get("prodUnd")})
        print("品种数:", len(codes), "| 抽样抓取全部 dto+surface 存档...")
        for i, code in enumerate(codes, 1):
            try:
                sur = fetch_surface(code)
                if sur:
                    fn = os.path.join(OUT, "surface_%s.json" % code)
                    json.dump(sur, open(fn, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=1)
                dto = fetch_dto(code)
                if dto:
                    fn = os.path.join(OUT, "dto_%s.json" % code)
                    json.dump(dto, open(fn, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=1)
            except Exception as e:
                print("[%d/%d] %s ERR %s" % (i, len(codes), code, e))
            time.sleep(SLEEP)
            if i % 10 == 0:
                print("  ... %d/%d" % (i, len(codes)))
        print("完成 ->", OUT)
    elif cmd == "surface":
        code = argv[1] if len(argv) > 1 else "SA"
        sur = fetch_surface(code)
        print(json.dumps(sur, ensure_ascii=False, indent=1)[:2000] if sur else "无数据")
    elif cmd == "dto":
        code = argv[1] if len(argv) > 1 else "SA"
        dto = fetch_dto(code)
        if dto:
            print(json.dumps(dto, ensure_ascii=False)[:1500])
    else:
        print("未知命令", cmd)


if __name__ == "__main__":
    main()