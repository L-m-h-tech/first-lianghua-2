# -*- coding: utf-8 -*-
"""装置退出联动关闭（run.py _record_launched/_shutdown_started）回归（零网络/零进程）。

覆盖：只记录亲手拉起的进程；退出时对记录的 PID 逐个 taskkill；
已在运行的软件（未记录）不受影响；taskkill 失败不抛异常。
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import device_config
import run


class _R:
    def __init__(self, rc=0):
        self.returncode = rc


def test_record_only_own_popen(monkeypatch):
    run._launched_pids = []
    class FakePopen:
        def __init__(self, *a, **kw):
            self.pid = 11111
    run._record_launched(FakePopen())
    assert run._launched_pids == [11111]
    # 不在运行/未 Popen 到的东西不记录
    run._record_launched(None)
    assert run._launched_pids == [11111]


def test_shutdown_kills_recorded_pids(monkeypatch):
    run._launched_pids = [11111, 22222]
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _R(0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run._shutdown_started()
    assert len(calls) == 2
    assert calls[0][:2] == ["taskkill", "/PID"]
    assert calls[0][2:] == ["11111", "/F", "/T"]
    assert calls[1][2] == "22222"
    assert run._launched_pids == []


def test_shutdown_noop_when_none(monkeypatch):
    run._launched_pids = []
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _R(0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run._shutdown_started()
    assert calls == []


def test_shutdown_kill_failure_silent(monkeypatch):
    run._launched_pids = [33333]

    def fake_run(cmd, **kw):
        raise OSError("taskkill 不可用")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run._shutdown_started()  # 不抛异常、不阻断退出
    assert run._launched_pids == []


# ---------------- _ensure_ths_debug_mode ----------------

_BASE_XML = '<?xml version="1.0" encoding="utf-8"?>\n<DataCenter>\n  <Debug>\n    <Cef>\n      <Console enable="true"/>\n    </Cef>\n  </Debug>\n</DataCenter>\n'


def test_ths_debug_already_enabled(tmp_path, monkeypatch):
    xml = tmp_path / "DataCenter.xml"
    xml.write_text(_BASE_XML, encoding="utf-8")
    monkeypatch.setattr(device_config, "CONFIG",
                        {"ths": {"debug_mode": True, "data_center_xml": str(xml)}})
    run._ensure_ths_debug_mode()
    assert not (tmp_path / "DataCenter.xml.bak").exists()


def test_ths_debug_patches_false(tmp_path, monkeypatch):
    xml = tmp_path / "DataCenter.xml"
    xml.write_text(_BASE_XML.replace('enable="true"', 'enable="false"'), encoding="utf-8")
    monkeypatch.setattr(device_config, "CONFIG",
                        {"ths": {"debug_mode": True, "data_center_xml": str(xml)}})
    run._ensure_ths_debug_mode()
    assert 'enable="true"' in xml.read_text(encoding="utf-8")
    assert (tmp_path / "DataCenter.xml.bak").exists()


def test_ths_debug_switch_off(tmp_path, monkeypatch):
    xml = tmp_path / "DataCenter.xml"
    xml.write_text(_BASE_XML.replace('enable="true"', 'enable="false"'), encoding="utf-8")
    monkeypatch.setattr(device_config, "CONFIG",
                        {"ths": {"debug_mode": False, "data_center_xml": str(xml)}})
    run._ensure_ths_debug_mode()
    assert 'enable="false"' in xml.read_text(encoding="utf-8")


def test_ths_debug_missing_file(monkeypatch):
    monkeypatch.setattr(device_config, "CONFIG",
                        {"ths": {"debug_mode": True, "data_center_xml": "/nonexistent/x.xml"}})
    run._ensure_ths_debug_mode()  # 不抛异常