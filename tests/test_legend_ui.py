# -*- coding: utf-8 -*-
"""legend_ui_collector 解析纯函数单测：零网络、零软件。

覆盖：行情行解析（列映射）、表格清洗、分钟聚合、期权腿解析、链组装、质量校验。
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import legend_ui_collector as L
import fusion


# ---------------- parse_quote_row ----------------

def test_parse_quote_row_by_name():
    cols = ["名称", "最新价", "涨跌幅", "成交量", "持仓量"]
    row = ["螺纹钢", "3756", "+0.8%", "234567", "890123"]
    mapping = {"variety": {"name": "名称"}, "price": {"name": "最新价"},
               "chg_pct": {"name": "涨跌幅"}, "volume": {"name": "成交量"},
               "open_interest": {"name": "持仓量"}}
    out = L.parse_quote_row(cols, row, mapping)
    assert out["variety"] == "螺纹钢"
    assert out["price"] == "3756"
    assert out["volume"] == "234567"


def test_parse_quote_row_by_idx():
    cols = ["a", "b", "c"]
    row = ["rb", "3900", "1.2"]
    out = L.parse_quote_row(cols, row, {"price": {"idx": 1}, "variety": {"idx": 0}})
    assert out["price"] == "3900"
    assert out["variety"] == "rb"


def test_parse_quote_row_missing_price():
    assert L.parse_quote_row(["a"], ["x"], {}) is None


def test_clean_rows_drops_blank():
    table = {"columns": ["a", "b"], "rows": [["1", "2"], ["", ""], ["3", "4"], ["注：测试"]]}
    cols, rows = L.clean_rows(table)
    assert len(rows) == 3
    assert cols == ["a", "b"]


# ---------------- MinuteAggregator ----------------

def test_aggregate_flush_across_minutes():
    agg = L.MinuteAggregator()
    snap1 = {"code": "rb2610", "variety": "螺纹钢", "price": 3756.0, "volume": 100,
             "ts": "2026-09-06 10:30:01"}
    snap2 = {"code": "rb2610", "variety": "螺纹钢", "price": 3760.0, "volume": 150,
             "ts": "2026-09-06 10:30:40"}
    b1, fl1 = agg.aggregate(snap1)
    assert b1["o"] == 3756.0 and b1["h"] == 3756.0
    b2, fl2 = agg.aggregate(snap2)
    assert b2["h"] == 3760.0 and b2["c"] == 3760.0
    # 跨分钟
    snap3 = {"code": "rb2610", "variety": "螺纹钢", "price": 3750.0, "volume": 200,
             "ts": "2026-09-06 10:31:05"}
    b3, fl3 = agg.aggregate(snap3)
    assert fl3 is not None
    assert fl3["c"] == 3760.0          # flush 的是上一分钟完整 bar
    assert fl3["dt"] == "2026-09-06 10:30:00"
    assert b3["o"] == 3750.0
    assert fl3["sym"] == "螺纹钢"


def test_aggregate_ignores_missing_price():
    agg = L.MinuteAggregator()
    b, fl = agg.aggregate({"code": "x", "price": None})
    assert b is None and fl is None


# ---------------- 期权腿 ----------------

def test_parse_option_leg():
    leg = L.parse_option_leg("cu2610C75000", last=500, bid=499, ask=501, oi=1200)
    assert leg["cp"] == "C"
    assert leg["strike"] == 75000.0
    assert leg["ask"] == 501
    assert L.parse_option_leg("不是期权代码") is None


def test_parse_option_leg_put():
    leg = L.parse_option_leg("m2609P2500", last=40)
    assert leg["cp"] == "P"
    assert leg["strike"] == 2500.0


# ---------------- 质量护栏 ----------------

def test_check_price_jump():
    assert fusion.check_price_jump(100.0, 102.0, 4.0)[0] is True
    assert fusion.check_price_jump(100.0, 106.0, 4.0)[0] is False
    assert fusion.check_price_jump(None, 5.0)[0] is True


def test_check_neg_spread():
    assert fusion.check_neg_spread(10.0, 10.2)[0] is True
    assert fusion.check_neg_spread(10.5, 10.2)[0] is False
    assert fusion.check_neg_spread(0, 10.0)[0] is True


def test_staleness():
    import time
    assert fusion.staleness_seconds(time.time() - 10) == pytest.approx(10, abs=2)
    assert fusion.staleness_seconds("2026-09-06 10:00:00") is not None
    assert fusion.staleness_seconds("") is None

# ---------------- _check_login（登录态检测） ----------------

class FakeConn:
    """模拟 CDP 连接的 eval 方法。"""
    def __init__(self, hash_val, submit_result=None, no_input=False):
        self._hash = hash_val
        self._submit = submit_result
        self._no_input = no_input
        self.calls = []

    def eval(self, expr):
        self.calls.append(expr)
        if "window.location.hash" in expr:
            return self._hash
        if "NO_INPUT" in expr or "querySelector" in expr and "input[type=" in expr if False else "querySelector" in expr:
            if self._no_input:
                return "NO_INPUT"
        return self._submit if self._submit is not None else "SUBMITTED"


def test_check_login_normal_hash():
    """hash 不含 login -> 正常返回 True，不触发登录。"""
    conn = FakeConn("#/market")
    status = fusion.StatusHub(path="/tmp/_test_login1.json")
    assert L._check_login(conn, status) is True
    assert len(conn.calls) == 1


def test_check_login_login_transition_no_creds():
    """hash 含 login 但无凭据 -> 返回 False。"""
    conn = FakeConn("#/login-transition")
    status = fusion.StatusHub(path="/tmp/_test_login2.json")
    # 让 legendary_credentials 返回空
    original = L.device_config.legend_credentials
    L.device_config.legend_credentials = lambda: []
    try:
        assert L._check_login(conn, status) is False
    finally:
        L.device_config.legend_credentials = original
