# -*- coding: utf-8 -*-
"""openvlab_collector 解析纯函数单测：零网络（用本地存档/内联样例）。

覆盖：ctamap 行解析、dto 行情解析、volatility-surface 腿解析、链组装。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openvlab_collector as O


# ---------------- parse_ctamap_rows ----------------

_CTAMAP = [
    {"product": "EG_O", "product_alias": "乙二醇", "prodUnd": "EG", "exchange": "DCE",
     "atmv_current": "52.22", "atmv_percentile": "90.53", "atmv_1dchg": "-1.11",
     "skew_current": "-0.05", "skew_percentile": "30.0", "ctn": "-0.0054",
     "price": "5866.0", "frontfwd_mom": "0.7161"},
    {"product": "SA_O", "product_alias": "纯碱", "prodUnd": "SA", "exchange": "CZCE",
     "atmv_current": "39.61", "price": "1078.0"},
    {"product": "X_O", "prodUnd": "", "atmv_current": "1.0"},   # 无代码 -> 跳过
]


def test_parse_ctamap_rows():
    out = O.parse_ctamap_rows(_CTAMAP)
    assert len(out) == 2
    first = out[0]
    assert first["code"] == "eg"
    assert first["variety"] == "乙二醇"
    assert first["price"] == 5866.0
    assert first["iv"] == 52.22
    assert first["iv_percentile"] == 90.53
    assert first["skew"] == -0.05
    assert first["ctn"] == -0.0054
    assert first["frontfwd_mom"] == 0.7161
    assert first["source"] == "openvlab"


def test_parse_ctamap_rows_empty():
    assert O.parse_ctamap_rows(None) == []
    assert O.parse_ctamap_rows([]) == []


# ---------------- parse_dto_quote ----------------

_DTO = {
    "headline": None,
    "context": {"r": {"1d": 0.015}, "i": {"s": [], "i": [
        {"n": "纯碱2611", "s": "SA2611", "l": 1078.0, "p": 1062.0,
         "b": 1077.0, "a": 1078.0, "v": 121365, "o": 366760}]}}
}


def test_parse_dto_quote():
    q = O.parse_dto_quote(_DTO, code="SA")
    assert q["variety"] == "纯碱2611"
    assert q["code"] == "sa2611"
    assert q["price"] == 1078.0
    assert q["bid"] == 1077.0
    assert q["ask"] == 1078.0
    assert q["volume"] == 121365
    assert q["open_interest"] == 366760
    assert q["source"] == "openvlab"


def test_parse_dto_quote_invalid():
    assert O.parse_dto_quote({}, code="SA") is None
    assert O.parse_dto_quote({"context": {"i": {"i": []}}}, code="SA") is None
    assert O.parse_dto_quote({"context": {"i": {"i": [{"l": 0}]}}}, code="SA") is None


# ---------------- parse_surface_legs ----------------

_SURFACE = {
    "202610": {
        "strike_poi_c": '{"1060.0": 100, "1080.0": 200}',
        "strike_poi_p": '{"1060.0": 50, "1080.0": 80}',
        "mktvol_tday_call_bid": "[[1060.0, 39.4], [1080.0, 40.0]]",
    },
    "202701": {"strike_poi_c": '{"1100.0": 10}', },
}


def test_parse_surface_legs_default_month():
    calls, puts = O.parse_surface_legs(_SURFACE, code="SA")
    assert len(calls) == 2
    assert len(puts) == 2
    assert calls[0]["strike"] == 1060.0 and calls[0]["oi"] == 100
    assert calls[1]["strike"] == 1080.0 and calls[1]["oi"] == 200
    assert calls[0]["cp"] == "C" and calls[0]["code"].endswith("C1060")
    assert puts[0]["cp"] == "P" and puts[0]["oi"] == 50


def test_parse_surface_legs_explicit_exp():
    calls, puts = O.parse_surface_legs(_SURFACE, exp="202701", code="SA")
    assert len(calls) == 1 and calls[0]["strike"] == 1100.0
    assert len(puts) == 0      # 该月无 put 数据 -> 不产出链


def test_parse_surface_legs_empty():
    calls, puts = O.parse_surface_legs({}, code="SA")
    assert calls == [] and puts == []
    calls, puts = O.parse_surface_legs(None, code="SA")
    assert calls == [] and puts == []


# ---------------- 链组装（需要 fusion.quant，mock 掉） ----------------

def _fake_quant():
    class _Ch:
        def build_summary(self, sym, ex, yy, mm, calls, puts):
            return {"sym": sym, "label": "%02d%02d" % (yy, mm), "pcr_oi": 0.5,
                    "n_call": len(calls), "n_put": len(puts),
                    "call_oi": sum(x["oi"] for x in calls),
                    "put_oi": sum(x["oi"] for x in puts),
                    "max_call_oi_strike": 1080.0, "atm_strike": None}
    return {"option_chain": _Ch()}


def test_chain_legs_to_rows(monkeypatch):
    monkeypatch.setattr(fusion_quant_target(), "quant", lambda: _fake_quant())
    calls, puts = O.parse_surface_legs(_SURFACE, exp="202610", code="SA")
    rows = O._chain_legs_to_rows(calls, puts, "sa", 26, 10, code="SA")
    assert rows is not None
    variety, chain = rows[0]
    assert variety == "SA"
    assert chain["label"] == "2610"
    assert chain["n_call"] == 2 and chain["n_put"] == 2
    assert chain["call_oi"] == 300 and chain["put_oi"] == 130


def test_chain_legs_to_rows_no_puts():
    calls, puts = O.parse_surface_legs({}, code="SA")
    assert O._chain_legs_to_rows(calls, puts, "sa", 26, 10) is None


# 辅助：让 monkeypatch 能打到 fusion.quant（openvlab_collector 内 import fusion）
def fusion_quant_target():
    import fusion
    return fusion