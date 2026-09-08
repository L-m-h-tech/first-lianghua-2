# -*- coding: utf-8 -*-
"""dashboard 显示页生成纯函数单测：离线、零网络。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dashboard


def test_render_html_basic():
    html = dashboard.render_html({})
    assert "<!DOCTYPE html>" in html
    assert "collector_status.json" in html      # 页面 JS fetch 的状态文件
    assert "quotes-body" in html
    assert "opts-body" in html
    assert "alerts" in html


def test_render_html_does_not_escape_breaks():
    html = dashboard.render_html({"quotes": []})
    assert "暂无行情" in html


def test_write_dashboard(tmp_path):
    path = tmp_path / "dashboard.html"
    out = dashboard.write_dashboard({"updated": "x"}, path=path)
    assert out == str(path)
    assert path.exists()
    assert "界面操作收集装置" in path.read_text(encoding="utf-8")


def test_collect_dashboard_data():
    from fusion import StatusHub
    s = StatusHub(path=str(tmp_path_marker() / "s.json"))
    s.update(collections=3, quotes=[{"code": "rb", "price": 100}])
    data = dashboard.collect_dashboard_data(s, include_quant=False)
    assert data["collections"] == 3
    assert "coverage" in data


def tmp_path_marker():
    import tempfile
    return Path(tempfile.mkdtemp())