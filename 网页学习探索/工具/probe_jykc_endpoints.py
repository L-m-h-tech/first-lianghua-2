# -*- coding: utf-8 -*-
"""probe_jykc_endpoints.py -- 批量探测 jiaoyikecha 数据端点的匿名可访问性与返回结构。

流程: 首页 → session.php(取PHPSESSID) → 对每个端点 POST（携带已知参数或空参数）记录 code/msg/data结构。
输出: 01_jiaoyikecha/数据/api_probe.json
"""
import json
import os
import re
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "01_jiaoyikecha", "数据", "api_probe.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BASE = "https://www.jiaoyikecha.com"

# (端点, 推荐参数, 说明) —— 参数参考真实页面请求
ENDPOINTS = [
    ("variety_position.php", {"variety": "螺纹钢", "code": "rb2701", "date": "2026-09-07"}, "品种持仓详情"),
    ("variety_prices_stat.php", {"variety": "螺纹钢", "code": "rb2701"}, "商品涨跌统计"),
    ("variety_net_position.php", {"variety": "螺纹钢", "code": "rb2701"}, "净持仓数据"),
    ("variety_trend.php", {"variety": "螺纹钢", "code": "rb2701"}, "商品持仓市值"),
    ("variety_structure.php", {"variety": "螺纹钢", "code": "rb2701"}, "持仓结构"),
    ("variety_profit_loss.php", {"variety": "螺纹钢", "code": "rb2701"}, "盈亏席位"),
    ("variety_code.php", {"variety": "螺纹钢", "code": ""}, "品种代码"),
    ("variety_contracts.php", {"variety": "螺纹钢"}, "品种合约列表"),
    ("variety_families.php", {}, "品种族"),
    ("all_varieties.php", {}, "全部品种"),
    ("official_indexes.php", {}, "官方指数"),
    ("index_prices_stat.php", {}, "指数涨跌统计"),
    ("index_money.php", {}, "指数持仓市值"),
    ("indexes_trend.php", {}, "指数资金动向"),
    ("indexes_pie.php", {}, "指数持仓结构饼图"),
    ("indexes_profit_loss.php", {}, "指数盈亏详情"),
    ("broker_positions.php", {}, "席位持仓列表"),
    ("broker_dates.php", {}, "席位日期范围"),
    ("broker_trend.php", {"broker": ""}, "大资金动向"),
    ("broker_pie.php", {}, "席位持仓结构"),
    ("broker_profit_loss.php", {"broker": ""}, "席位盈亏商品"),
    ("broker_calendar.php", {}, "盈亏日历"),
    ("broker_pk.php", {"broker1": "", "broker2": ""}, "席位对对碰"),
    ("broker_table.php", {}, "席位大全"),
    ("broker_variety.php", {"broker": ""}, "席位品种"),
    ("all_brokers.php", {}, "全部席位"),
    ("recent_contracts.php", {"variety": "螺纹钢"}, "最近合约"),
    ("contract_dates.php", {"variety": "螺纹钢", "code": ""}, "合约日期范围"),
    ("deepview_lhnx.php", {}, "龙虎牛熊一览"),
    ("longhu_list.php", {}, "龙虎榜"),
    ("niuxiong_list.php", {}, "牛熊榜"),
    ("deepview_strategies.php", {}, "龙虎牛熊分析"),
    ("deepview_brokers.php", {}, "席位四象图"),
    ("prices_map.php", {}, "热度图"),
    ("hg.php", {}, "支撑压力位"),
    ("qk.php", {}, "乾坤归一"),
    ("speculation.php", {}, "商品投机度"),
    ("correlation.php", {}, "相关性分析(可能需要参数)"),
    ("toolbox_foreign.php", {}, "盘后外盘涨跌"),
    ("market_temp.php", {}, "多空领先(首页)"),
    ("market_temp_line.php", {}, "多空领先指标"),
    ("unusual_quotes.php", {}, "异动行情"),
    ("temp_quotes.php", {}, "领先指标行情"),
    ("fundamental_db.php", {"variety": "螺纹钢"}, "基本面数据库"),
    ("fundamental_db_info.php", {}, "基本面数据(毛利等)"),
    ("all_varieties_db.php", {}, "基本面库品种"),
    ("items_by_variety.php", {"variety": "螺纹钢"}, "品种数据项"),
    ("spots_list.php", {}, "现货报价"),
    ("spots.php", {"variety": ""}, "现货详情"),
    ("arbitrage_basis_all.php", {}, "基差一览"),
    ("arbitrage_fut_spot_structure_all.php", {}, "期限一览"),
    ("arbitrage_warehouse.php", {}, "仓单查询"),
    ("daily_wr.php", {}, "仓单日报"),
    ("wr_dates.php", {}, "仓单日期"),
    ("gdp.php", {}, "经济数据"),
    ("fund_compare.php", {}, "资金市值对比"),
    ("fund_deal_pie.php", {}, "成交额分布"),
    ("fund_bs_pie.php", {}, "净持仓分布"),
    ("fund_big_chge.php", {}, "机构动向"),
    ("fund_all.php", {}, "持仓全景图"),
    ("fund_dates.php", {}, "资金日期"),
    ("reports_list.php", {}, "精选研报列表"),
    ("v2/aireport", {}, "AI研报"),
    ("v2/aireportHot", {}, "AI研报热榜"),
    ("report_brokers.php", {}, "研报席位"),
    ("net_position_list.php", {"variety": "螺纹钢"}, "净持仓列表"),
    ("index_show.php", {}, "指数详情"),
]


def main():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": BASE + "/www.jiaoyikecha.com"})
    s.get(BASE + "/www.jiaoyikecha.com", timeout=20)
    r0 = s.post(BASE + "/ajax/session.php?v=5f6760cc", timeout=20)
    try:
        sid = (r0.json().get("cookie") or {}).get("PHPSESSID")
        if sid:
            s.cookies.set("PHPSESSID", sid)
    except Exception:
        pass
    print("session ready, cookies:", dict(s.cookies))

    results = []
    for ep, params, desc in ENDPOINTS:
        url = f"{BASE}/ajax/{ep}" + ("?v=5f6760cc" if ".php" in ep else "")
        try:
            r = s.post(url, data=params, timeout=25)
            body = r.text
            try:
                d = r.json()
                code = d.get("code")
                msg = d.get("msg")
                data = d.get("data")
                shape = describe(data)
            except Exception:
                code, msg, shape = "nonjson", "", f"len={len(body)}"
            rec = {"ep": ep, "desc": desc, "status": r.status_code, "code": code,
                   "msg": (msg or "")[:60], "shape": shape, "body_preview": body[:300]}
        except Exception as e:
            rec = {"ep": ep, "desc": desc, "status": "err", "code": None,
                   "msg": str(e)[:80], "shape": ""}
        results.append(rec)
        print(f"{ep:42s} code={rec['code']!s:6s} {str(rec['shape'])[:70]}", flush=True)
        time.sleep(0.4)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("saved:", OUT)


def describe(data):
    if isinstance(data, list):
        if not data:
            return "[]"
        return f"list[{len(data)}] sample={json.dumps(data[0], ensure_ascii=False)[:150]}"
    if isinstance(data, dict):
        if not data:
            return "{}"
        return f"dict keys={list(data.keys())[:12]}"
    if data is None:
        return "None"
    return f"{type(data).__name__} len={len(str(data))}"


if __name__ == "__main__":
    main()