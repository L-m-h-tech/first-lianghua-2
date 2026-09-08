# -*- coding: utf-8 -*-
"""jiaoyikecha_collector 解析纯函数单测：零网络（内联样例，字段结构来自真实抓包）。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jiaoyikecha_collector as J


# ---------------- parse_warehouse_receipts（仓单日报） ----------------

_WR = [
    {"name": "螺纹钢", "wr_unit": 0.1, "total_vol": 134546, "total_chge": 0,
     "total_vol2": 13454.6, "total_chge2": 0, "chge_rate": 0},
    {"name": "纯碱", "wr_unit": 1, "total_vol": 88000, "total_chge": 1200,
     "total_vol2": 88000, "total_chge2": 1200, "chge_rate": 1.3},
]


def test_parse_warehouse_receipts():
    out = J.parse_warehouse_receipts(_WR, date="2026-09-08")
    assert len(out) == 2
    r0 = out[0]
    assert r0["item_type"] == "wr"
    assert r0["code"] == "螺纹钢"
    assert r0["data_date"] == "2026-09-08"
    assert r0["value"]["total_vol"] == 134546
    assert r0["value"]["wr_unit"] == 0.1
    assert r0["source"] == "jiaoyikecha"
    assert out[1]["value"]["chge_rate"] == 1.3


def test_parse_warehouse_receipts_empty():
    assert J.parse_warehouse_receipts(None) == []
    assert J.parse_warehouse_receipts([]) == []


# ---------------- parse_longhu / parse_niuxiong（龙虎/牛熊榜） ----------------

def test_parse_longhu():
    out = J.parse_longhu([{"name": "沪金", "code": "au2612", "longhu": 82.81466271334432}],
                         date="2026-09-08")
    assert out[0]["item_type"] == "longhu"
    assert out[0]["code"] == "au2612"
    assert out[0]["variety"] == "沪金"
    assert out[0]["value"]["longhu"] == pytest.approx(82.81466271334432)


def test_parse_niuxiong():
    out = J.parse_niuxiong([{"name": "沪金", "code": "au2702", "niuxiong": 50}],
                           date="2026-09-08")
    assert out[0]["item_type"] == "niuxiong"
    assert out[0]["code"] == "au2702"
    assert out[0]["value"]["niuxiong"] == 50


# ---------------- parse_hg（支撑压力位） ----------------

_HG = [
    {"variety": "20号胶", "code": "nr2611", "current_price": 16580, "time": "23:00:00",
     "min3": "<span style='color: #aaa; font-size: 12px;'>VIP用户可查看</span><br>"
             "<a lay-href='/vip' class='layui-btn'>我要充值</a>",
     "min15": "<span class='win'>偏多</span>，支撑：16115-16145",
     "min60": "<span style='color: #aaa;'>VIP用户可查看</span>"},
    {"variety": "", "code": "", "current_price": None},
]


def test_parse_hg():
    out = J.parse_hg(_HG, date="2026-09-08")
    assert len(out) == 1               # 无 code 的行跳过
    r = out[0]
    assert r["code"] == "nr2611"
    assert r["value"]["current_price"] == 16580
    assert r["value"]["min15"] == "偏多，支撑：16115-16145"   # HTML 已剥离
    assert "VIP" in r["value"]["min3"]                        # 文本保留，标签剥离


# ---------------- parse_broker_trend（席位资金） ----------------

def test_parse_broker_trend():
    out = J.parse_broker_trend(
        [{"name": "国泰君安", "grade": "A", "money": 1904738480,
          "order_money": 1904738480, "variety": "1000中证"}], date="2026-09-08")
    assert out[0]["item_type"] == "broker_trend"
    assert out[0]["code"] == "国泰君安"
    assert out[0]["value"]["grade"] == "A"
    assert out[0]["value"]["money"] == 1904738480


# ---------------- parse_net_positions（席位净持仓） ----------------

def test_parse_net_positions():
    out = J.parse_net_positions(
        [{"broker": "上海中期", "net_position": 600, "net_position_chge": 270}],
        variety="螺纹钢", date="2026-09-08")
    assert out[0]["item_type"] == "net_position"
    assert out[0]["code"] == "上海中期"
    assert out[0]["variety"] == "螺纹钢"
    assert out[0]["value"]["net_position"] == 600
    assert out[0]["value"]["net_position_chge"] == 270


# ---------------- parse_all_varieties（品种表） ----------------

def test_parse_all_varieties():
    out = J.parse_all_varieties(
        [{"market": "上期所", "name": "螺纹钢", "symbol": "RB"}], date="2026-09-08")
    assert out[0]["item_type"] == "variety"
    assert out[0]["code"] == "RB"
    assert out[0]["variety"] == "螺纹钢"
    assert out[0]["value"]["market"] == "上期所"


# ---------------- _to_float / _strip_html 工具 ----------------

def test_to_float():
    assert J._to_float("1,234") is None or J._to_float("1234.5") == 1234.5
    assert J._to_float(None) is None
    assert J._to_float("") is None
    assert J._to_float("abc") is None


def test_strip_html():
    assert J._strip_html("<span class='win'>偏多</span>，支撑：16115") == "偏多，支撑：16115"
    assert J._strip_html(None) == ""
    assert J._strip_html("") == ""


# ---------------- 状态摘要 ----------------

def test_status_summary_groups_by_type():
    rows = J.parse_warehouse_receipts(_WR, date="2026-09-08") + \
        J.parse_longhu([{"name": "沪金", "code": "au2612", "longhu": 82.8}], date="2026-09-08")
    s = J._status_summary(rows, "2026-09-08")
    assert s["date"] == "2026-09-08"
    assert "wr" in s and "longhu" in s
    # wr 按 total_vol 降序：纯碱 88000 > 螺纹钢 134546？不——134546 > 88000，螺纹钢在前
    assert s["wr"][0]["code"] == "螺纹钢"