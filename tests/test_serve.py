# -*- coding: utf-8 -*-
"""显示页服务（run.py _make_device_server）回归（第23轮）：构建成功/端口被占返 None/serve_with_daemon 开关。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run


def test_make_server_ok_then_port_busy(monkeypatch):
    # 用随机高位端口构建：成功返回 server；同端口再建返回 None（端口被占跳过）
    monkeypatch.setitem(run.CONFIG["http"], "serve_port", 0)   # 0 = 系统分配临时端口
    srv = run._make_device_server()
    assert srv is not None
    try:
        port = srv.server_address[1]
        monkeypatch.setitem(run.CONFIG["http"], "serve_port", port)
        srv2 = run._make_device_server()
        assert srv2 is None                                     # 同端口被占 → None（daemon 内静默跳过）
    finally:
        srv.server_close()


def test_make_device_server_uses_config_host(monkeypatch):
    monkeypatch.setitem(run.CONFIG["http"], "serve_port", 0)
    srv = run._make_device_server()
    assert srv is not None
    try:
        assert srv.server_address[0] == run.CONFIG["http"]["serve_host"]
    finally:
        srv.server_close()
