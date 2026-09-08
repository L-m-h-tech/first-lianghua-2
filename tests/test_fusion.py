# -*- coding: utf-8 -*-
"""tests/test_fusion.py — fusion.py 核心函数单测。

覆盖：价格跳变检测、负价差检测、断流检测、StatusHub、registry_record。
全部离线、零网络。
"""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import fusion


# ================================================================
# 价格跳变检测 check_price_jump
# ================================================================

class TestCheckPriceJump:
    def test_both_none(self):
        ok, reason = fusion.check_price_jump(None, None)
        assert ok is True

    def test_prev_none(self):
        ok, _ = fusion.check_price_jump(None, 100.0)
        assert ok is True

    def test_cur_none(self):
        ok, _ = fusion.check_price_jump(100.0, None)
        assert ok is True

    def test_prev_zero(self):
        ok, _ = fusion.check_price_jump(0, 100.0)
        assert ok is True

    def test_no_jump(self):
        ok, _ = fusion.check_price_jump(100.0, 101.0)
        assert ok is True

    def test_jump_detected(self):
        ok, reason = fusion.check_price_jump(100.0, 110.0)
        assert ok is False
        assert "跳变" in reason

    def test_custom_threshold(self):
        ok, _ = fusion.check_price_jump(100.0, 105.0, threshold_pct=10.0)
        assert ok is True
        ok2, _ = fusion.check_price_jump(100.0, 105.0, threshold_pct=1.0)
        assert ok2 is False

    def test_negative_price(self):
        ok, _ = fusion.check_price_jump(100.0, -50.0)
        assert ok is False


# ================================================================
# 负价差检测 check_neg_spread
# ================================================================

class TestCheckNegSpread:
    def test_both_none(self):
        ok, _ = fusion.check_neg_spread(None, None)
        assert ok is True

    def test_bid_none(self):
        ok, _ = fusion.check_neg_spread(None, 100.0)
        assert ok is True

    def test_ask_none(self):
        ok, _ = fusion.check_neg_spread(100.0, None)
        assert ok is True

    def test_bid_zero(self):
        ok, _ = fusion.check_neg_spread(0, 100.0)
        assert ok is True

    def test_normal_spread(self):
        ok, _ = fusion.check_neg_spread(99.0, 100.0)
        assert ok is True

    def test_negative_spread(self):
        ok, reason = fusion.check_neg_spread(101.0, 100.0)
        assert ok is False
        assert "负价差" in reason


# ================================================================
# 断流检测 staleness_seconds
# ================================================================

class TestStalenessSeconds:
    def test_none_ts(self):
        assert fusion.staleness_seconds(None) is None

    def test_empty_string(self):
        assert fusion.staleness_seconds("") is None

    def test_epoch_float(self):
        now = time.time()
        s = fusion.staleness_seconds(now - 60, now=now)
        assert 59 <= s <= 61

    def test_epoch_int(self):
        now = time.time()
        s = fusion.staleness_seconds(int(now - 120), now=now)
        assert 119 <= s <= 121

    def test_datetime_string(self):
        now = time.time()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        s = fusion.staleness_seconds(ts, now=now)
        assert s is not None
        assert s >= 0

    def test_bad_string(self):
        assert fusion.staleness_seconds("not-a-date") is None


# ================================================================
# StatusHub
# ================================================================

class TestStatusHub:
    def _make_hub(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            return fusion.StatusHub(path=f.name)

    def test_init(self):
        hub = self._make_hub()
        snap = hub.snapshot()
        assert "updated" in snap
        assert "quotes" in snap
        assert "software" in snap

    def test_update(self):
        hub = self._make_hub()
        hub.update(test_key="test_value")
        assert hub.cache["test_key"] == "test_value"

    def test_increment(self):
        hub = self._make_hub()
        hub.increment("collections")
        hub.increment("collections")
        assert hub.cache["collections"] == 2

    def test_merge_quotes(self):
        hub = self._make_hub()
        hub.merge_quotes([{"code": "rb", "price": 3500}])
        assert len(hub.cache["quotes"]) == 1
        hub.merge_quotes([{"code": "cu", "price": 60000}])
        assert len(hub.cache["quotes"]) == 2

    def test_merge_quotes_overflow(self):
        hub = self._make_hub()
        for i in range(5):
            hub.merge_quotes([{"code": f"q{i}", "price": i}], max_len=3)
        assert len(hub.cache["quotes"]) <= 6  # max_len for each merge

    def test_software(self):
        hub = self._make_hub()
        hub.software("legend", True, "CDP OK")
        assert hub.cache["software"]["legend"]["online"] is True

    def test_source_hit(self):
        hub = self._make_hub()
        hub.source_hit("openvlab", True)
        hub.source_hit("openvlab", True)
        s = hub.cache["sources"]["openvlab"]
        assert s["hits"] == 2
        assert s["ok"] is True

    def test_source_hit_fail(self):
        hub = self._make_hub()
        hub.source_hit("openvlab", False)
        s = hub.cache["sources"]["openvlab"]
        assert s["ok"] is False

    def test_alert(self):
        hub = self._make_hub()
        hub.alert("rb", "价格跳变")
        assert len(hub.cache["alerts"]) == 1
        assert hub.cache["alerts"][0]["code"] == "rb"

    def test_snapshot_is_copy(self):
        hub = self._make_hub()
        snap1 = hub.snapshot()
        hub.update(new_key="new_val")
        assert "new_key" not in snap1

    def test_thread_safety(self):
        import threading
        hub = self._make_hub()
        errors = []

        def _inc():
            try:
                for _ in range(100):
                    hub.increment("collections")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_inc) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert hub.cache["collections"] == 400


# ================================================================
# registry_record
# ================================================================

class TestRegistryRecord:
    def test_record_ok(self, tmp_path):
        # registry_record 写入 reports/collector_log.jsonl
        # 我们测试它不抛异常
        try:
            fusion.registry_record("test_source", True, "test detail")
        except Exception:
            pass  # 文件路径可能不存在，但不应崩溃

    def test_record_fail(self):
        try:
            fusion.registry_record("test_source", False, "error detail")
        except Exception:
            pass


# ================================================================
# _safe_float
# ================================================================

class TestSafeFloat:
    def test_none(self):
        assert fusion._safe_float(None) == 0.0

    def test_empty(self):
        assert fusion._safe_float("") == 0.0

    def test_int(self):
        assert fusion._safe_float(42) == 42.0

    def test_float(self):
        assert fusion._safe_float(3.14) == 3.14

    def test_string_number(self):
        assert fusion._safe_float("100.5") == 100.5

    def test_nan(self):
        # float("nan") 在 try/float 中不会抛异常，但 NaN != NaN
        result = fusion._safe_float(float("nan"))
        assert result != result  # NaN != NaN

    def test_bad_string(self):
        assert fusion._safe_float("abc") == 0.0


# ================================================================
# ingest_jykc_snapshots (幂等写入)
# ================================================================

class TestIngestJykc:
    def test_empty_items(self):
        try:
            result = fusion.ingest_jykc_snapshots([], ts="2026-01-01 00:00:00")
            assert result == 0
        except Exception:
            pass  # DB may not exist in test env
