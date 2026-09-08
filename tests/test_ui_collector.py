# -*- coding: utf-8 -*-
"""ui_collector.py 单元测试：parse_tsv、normalize_number、is_ready。"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import ui_collector


# ======================== parse_tsv ========================

class TestParseTsv:
    def test_empty(self):
        assert ui_collector.parse_tsv("") is None

    def test_single_row(self):
        result = ui_collector.parse_tsv("col1\tcol2\tcol3")
        assert result is not None
        assert "columns" in result
        assert "rows" in result
        assert len(result["rows"]) == 1
        assert result["rows"][0] == ["col1", "col2", "col3"]

    def test_multi_row(self):
        result = ui_collector.parse_tsv("a\tb\nc\td")
        assert result is not None
        # First row becomes columns, rest become rows
        assert result["columns"] == ["a", "b"]
        assert result["rows"] == [["c", "d"]]

    def test_trailing_newline(self):
        result = ui_collector.parse_tsv("a\tb\n")
        assert result is not None
        assert result["rows"] == [["a", "b"]]

    def test_whitespace_cells(self):
        result = ui_collector.parse_tsv("  a  \t  b  ")
        assert result is not None
        # Whitespace is stripped
        assert result["rows"][0] == ["a", "b"]

    def test_has_timestamp(self):
        result = ui_collector.parse_tsv("a\tb")
        assert "ts" in result


# ======================== normalize_number ========================

class TestNormalizeNumber:
    def test_none(self):
        assert ui_collector.normalize_number(None) is None

    def test_empty(self):
        assert ui_collector.normalize_number("") is None

    def test_plain_int(self):
        assert ui_collector.normalize_number("123") == 123.0

    def test_plain_float(self):
        assert ui_collector.normalize_number("12.5") == 12.5

    def test_comma_separated(self):
        assert ui_collector.normalize_number("1,234.56") == 1234.56

    def test_negative(self):
        assert ui_collector.normalize_number("-3.5") == -3.5

    def test_non_numeric(self):
        assert ui_collector.normalize_number("abc") is None

    def test_percentage_not_supported(self):
        # normalize_number does not handle % suffix
        assert ui_collector.normalize_number("5.5%") is None

    def test_chinese_unit_not_supported(self):
        # normalize_number does not handle 万/亿 suffix
        assert ui_collector.normalize_number("1.5万") is None


# ======================== is_ready ========================

class TestIsReady:
    def test_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            assert ui_collector.is_ready(path, poll_sec=1.0) is True
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        assert ui_collector.is_ready("/tmp/_nonexistent_file_xyz", poll_sec=0.5) is False

    def test_path_object(self):
        p = Path(tempfile.mktemp())
        p.touch()
        try:
            assert ui_collector.is_ready(p, poll_sec=1.0) is True
        finally:
            p.unlink()


# ======================== read_clipboard_text ========================
# 注：clipboard 测试在某些环境下会触发 Windows 访问冲突，跳过
