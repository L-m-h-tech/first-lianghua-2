# -*- coding: utf-8 -*-
"""界面操作原语层：CDP / UIA 双适配器 + 剪贴板 + 截图/OCR。

架构（参考 easytrader 的 SourceAdapter 模式）：
- 每个适配器实现统一接口：connect / read / click / scroll / snapshot / disconnect；
- 统一表格结构：{"columns": [...], "rows": [[...]], "source": "...", "ts": "..."}；
- 业务采集器按"结构化(DOM/控件树) -> 剪贴板 -> OCR"三级策略调用；
- 所有第三方库延迟导入：本模块 import 零依赖（离线单测友好），缺库只降级不崩。

只做本地个人研究用途，控制采集频率。
"""
import json
import re
import subprocess
import time
from datetime import datetime

import device_config


class AdapterError(Exception):
    """适配器层统一异常：连接失败/控件缺失/解析失败均抛此类型。"""


# ---------------------------------------------------------------- 表格工具

def parse_tsv(text):
    """剪贴板制表符文本 -> 统一表格结构（easytrader Copy 模式的解析端）。"""
    if not text:
        return None
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    rows = [[c.strip() for c in ln.split("\t")] for ln in lines if ln.strip()]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    # 首行若是列名且该列后续有变化，视为表头
    columns = rows[0] if len(rows) > 1 else None
    body = rows[1:] if columns else rows
    return {"columns": columns, "rows": body, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}


def normalize_number(s):
    """行情文本数字 -> float；失败返回 None。去掉千分位逗号/百分比/正负号处理由调用方做。"""
    if s is None:
        return None
    t = str(s).replace(",", "").replace("％", "%").strip()
    m = re.match(r"^[+-]?\d+(\.\d+)?$", t)
    return float(t) if m else None


# ---------------------------------------------------------------- 进程/端口探测

def find_process_ports(keywords, port_scan=None):
    """按进程名关键字定位监听端口（Windows：tasklist + netstat）。
    返回 {pid: [port,...]}；port_scan 可给候选端口表做 HTTP 探测补充。"""
    out = {}
    try:
        tl = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, timeout=20).stdout
        pids = []
        for line in tl.splitlines():
            if any(k.lower() in line.lower() for k in keywords):
                m = re.search(r'"(\d+)"\s*$', line)
                if m:
                    pids.append(m.group(1))
        if not pids:
            return out
        ns = subprocess.run(["netstat", "-ano"],
                            capture_output=True, text=True, timeout=20).stdout
        for line in ns.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] in ("TCP", "UDP") and any(p in parts[-1] for p in pids):
                m = re.search(r":(\d+)\s*$", parts[1] if parts[0] == "TCP" else parts[1])
                if m:
                    out.setdefault(parts[-1], []).append(int(m.group(1)))
    except Exception:
        pass
    return out


def is_ready(path, poll_sec=10.0, interval=0.5):
    """等待文件/资源就绪（返回 bool）。用于等待软件进程/调试口出现。"""
    from pathlib import Path
    if isinstance(path, Path) or (isinstance(path, str) and not path.startswith(("http://", "https://", "ws://"))):
        p = Path(path)
        deadline = time.time() + poll_sec
        while time.time() < deadline:
            if p.exists():
                return True
            time.sleep(interval)
        return p.exists()
    deadline = time.time() + poll_sec
    while time.time() < deadline:
        try:
            import urllib.request
            urllib.request.urlopen(path, timeout=1)
            return True
        except Exception:
            time.sleep(interval)
    return False


# ---------------------------------------------------------------- CDP 适配器（Electron/Chromium）

_WS_TIMEOUT = 8


class CdpAdapter:
    """Chrome DevTools Protocol 适配器：探测调试端口 -> 读 DOM 表格/点击/滚动。

    与量化项目 browser_reader 同款方案（websocket-client + Runtime.evaluate），
    但支持通用表格提取与操作，供 Legend（Electron）使用。
    """

    def __init__(self, port=None):
        self.port = port or device_config.CONFIG["legend"].get("cdp_port", 9225)
        self._tabs = []
        self._page = None
        self.connected = False
        self.last_error = None

    # ---- 连接 ----
    def connect(self, port_candidates=None):
        """探测 http://127.0.0.1:<port>/json，成功即接入；返回 bool。"""
        import urllib.request
        candidates = list(dict.fromkeys([self.port] + list(port_candidates or [])))
        for p in candidates:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{p}/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode("utf-8", "replace"))
                self.port = p
                self._tabs = [t for t in tabs if t.get("type") == "page"]
                self.connected = bool(self._tabs) or True
                return True
            except Exception as e:
                self.last_error = str(e)
                continue
        self.connected = False
        return False

    def pages(self):
        return [{"title": t.get("title", ""), "url": t.get("url", "")}
                for t in self._tabs]

    def find_page(self, url_kw):
        for t in self._tabs:
            if url_kw in (t.get("url") or ""):
                self._page = t
                return t
        return None

    def _ws(self):
        import websocket
        ws_url = self._page.get("webSocketDebuggerUrl")
        if not ws_url:
            raise AdapterError("未选中 CDP 页面")
        return ws_url

    def eval(self, expr, timeout=_WS_TIMEOUT):
        import websocket
        ws = websocket.create_connection(self._ws(), timeout=timeout, suppress_origin=True)
        try:
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                "params": {"expression": expr, "returnByValue": True}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == 1:
                    res = msg.get("result", {}).get("result", {})
                    if res.get("exceptionDetails"):
                        raise AdapterError("CDP 执行异常: %s" %
                                           str(res["exceptionDetails"])[:200])
                    return res.get("value")
        finally:
            ws.close()

    # ---- 读取 ----
    def _table_extract_js(self):
        return r"""
(function(){
  function rowsOf(t){ var rows=[];
    t.querySelectorAll('tr').forEach(function(tr){
      var cs=Array.from(tr.querySelectorAll('th,td')).map(function(c){return (c.innerText||'').trim();});
      if(cs.length) rows.push(cs);
    });
    return rows;
  }
  var out=[];
  var seen=0;
  document.querySelectorAll('table').forEach(function(t){
    if(seen>15) return;
    var rows=rowsOf(t);
    if(rows.length>1){ seen++; out.push({tag:'table', cols:rows[0], rows:rows.slice(1), n:rows.length}); }
  });
  if(!out.length){
    document.querySelectorAll('[role="row"], .row, .el-table__row').forEach(function(t,ix){
      if(seen>15) return;
      var cs=Array.from(t.querySelectorAll('[role="cell"], td, .cell')).map(function(c){return (c.innerText||'').trim();});
      if(cs.length){ seen++; out.push({tag:'rowlist', cols:null, rows:[cs], n:1}); }
    });
  }
  if(!out.length){
    var pre=document.body.innerText.split('\n').map(function(s){return s.trim();}).filter(Boolean);
    out.push({tag:'text', cols:null, rows:pre.slice(0,200).map(function(s){return [s];}), n:pre.length});
  }
  return JSON.stringify(out);
})()
"""

    def read_table(self, pick=0, timeout=_WS_TIMEOUT):
        """提取页面表格候选（pick 为候选序号，0=最大尺寸候选）；失败抛 AdapterError。"""
        raw = self.eval(self._table_extract_js(), timeout=timeout)
        cands = json.loads(raw or "[]")
        if not cands:
            raise AdapterError("页面无可提取表格")
        best = max(cands, key=lambda c: c.get("n", 0)) if pick == 0 else cands[min(pick, len(cands) - 1)]
        return {"columns": best.get("cols"), "rows": best.get("rows") or [],
                "table_tag": best.get("tag"), "source": "legend_cdp",
                "ts": time.strftime("%Y-%m-%d %H:%M:%S")}

    def read_body_text(self):
        return (self.eval("document.body.innerText") or "")

    def select_probe(self):
        """--probe 用：返回全部候选表格的行列数与首行样例，供人工固化 selectors。"""
        raw = self.eval(self._table_extract_js())
        cands = json.loads(raw or "[]")
        return [{"tag": c.get("tag"), "n": c.get("n"), "cols": (c.get("cols") or [])[:6],
                 "first_row": (c.get("rows") or [[]])[0][:6]} for c in cands]

    # ---- 操作 ----
    def click(self, css):
        ok = self.eval(f"""(function(){{var el=document.querySelector({json.dumps(css)});
            if(!el) return false; el.click(); return true;}})()""")
        if not ok:
            raise AdapterError(f"点击选择器未命中: {css}")
        return True

    def scroll(self, dy=600):
        self.eval(f"window.scrollBy(0,{int(dy)}); true")

    def open_url(self, url):
        import urllib.request
        urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/new?{url}", timeout=4)
        time.sleep(3)
        self.connect()

    def disconnect(self):
        self.connected = False
        self._page = None


# ---------------------------------------------------------------- UIA 适配器（WPF/自绘窗口兜底）

class UiaAdapter:
    """uiautomation 适配器：定位窗口、读文本/控件树、点击、截图。

    对自绘网格多数字内容不可读——业务层应先试剪贴板(^A^C)再试 OCR。
    """

    def __init__(self, name_re="期货通"):
        self.name_re = name_re
        self.window = None
        self.connected = False
        self.last_error = None

    def connect(self, poll_sec=10):
        import uiautomation as auto
        deadline = time.time() + poll_sec
        while time.time() < deadline:
            try:
                wins = [w for w in auto.GetRootControl().GetChildren()
                        if self.name_re in (w.Name or "")][:1]
                if wins:
                    self.window = wins[0]
                    self.connected = True
                    return True
            except Exception as e:
                self.last_error = str(e)
            time.sleep(0.5)
        self.connected = False
        return False

    def focus(self):
        if self.window:
            self.window.SetActive()
            self.window.SetTopmost(True)
            time.sleep(0.3)
            self.window.SetTopmost(False)

    def dump_tree(self, max_depth=4, max_items=400):
        """控件树快照文本（--probe 摸底 / 版本兼容诊断用）。"""
        if not self.window:
            return ""
        lines = []

        def walk(ctrl, depth):
            if len(lines) >= max_items or depth > max_depth:
                return
            try:
                nm = (ctrl.Name or "")[:40]
                ct = getattr(ctrl, "ControlTypeName", "") or ""
                cl = (getattr(ctrl, "ClassName", "") or "")[:40]
                if nm or ct:
                    lines.append("  " * depth + f"{ct}|{cl}|{nm}")
            except Exception:
                return
            for ch in ctrl.GetChildren()[:12]:
                walk(ch, depth + 1)

        walk(self.window, 0)
        self.last_dump = "\n".join(lines)
        return self.last_dump

    def read_all_text(self, max_n=2000):
        """收集窗口内全部可读文本（Name/Value），自绘网格大概率只有空表头。"""
        out = []
        if not self.window:
            return ""
        queue = [self.window]
        while queue and len(out) < max_n:
            c = queue.pop(0)
            try:
                for attr in ("Name", "Value"):
                    v = getattr(c, attr, None)
                    if v and str(v).strip():
                        out.append(str(v).strip())
            except Exception:
                pass
            try:
                queue.extend(c.GetChildren())
            except Exception:
                pass
        return "\n".join(dict.fromkeys(out))[:20000]

    def find(self, control_type=None, name_re=None, class_re=None, top=None):
        """按规则找一个控件；规则读 selectors 或直接传参。"""
        import uiautomation as auto
        root = self.window or auto.GetRootControl()
        if control_type == "Window":
            return root
        ct = {"Button": auto.ButtonControl, "Edit": auto.EditControl,
              "Table": auto.TableControl, "ListItem": auto.ListItemControl,
              "Text": auto.TextControl, "DataItem": auto.DataItemControl,
              "Custom": auto.CustomControl}.get(control_type or "")
        if ct:
            try:
                return ct(root, Name=name_re, ClassName=class_re, searchDepth=8).Exists(3)
            except Exception:
                return None
        return None

    def click_control(self, ctrl):
        if ctrl is None:
            raise AdapterError("目标控件不存在（可能版本不兼容，见控件树快照）")
        try:
            ctrl.Click()
            return True
        except Exception as e:
            raise AdapterError(f"点击失败: {e}")

    def send_keys(self, keys):
        import uiautomation as auto
        self.focus()
        # 兼容两种传参：字符串 "^ac" 或列表 ["^a", "^c"]
        if isinstance(keys, (list, tuple)):
            keys = "".join(keys)
        auto.SendKeys(keys, interval=0.03)

    def snapshot(self, save_path):
        """截取窗口区域 PNG（Pillow）。"""
        from PIL import ImageGrab
        if not self.window:
            return None
        r = self.window.BoundingRectangle
        img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
        img.save(save_path, "PNG")
        return str(save_path)

    def disconnect(self):
        self.connected = False
        self.window = None


# ---------------------------------------------------------------- 剪贴板（纯 ctypes）

def read_clipboard_text():
    """读取 Windows 剪贴板 Unicode 文本；无文本返回 None。纯标准库（ctypes）。"""
    import ctypes
    user32 = ctypes.windll.user32
    # 64 位 Windows：句柄/指针需 c_void_p / WPARAM 宽度，否则 GetClipboardData 返回被截断
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.LocalLock.restype = ctypes.c_void_p
    if not user32.OpenClipboard(0):
        return None
    try:
        CF_UNICODETEXT = 13
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            n = kernel32.GlobalSize(h)
            buf = ctypes.create_string_buffer(int(n))
            ctypes.memmove(buf, p, int(n))
            text = buf.raw.decode("utf-16-le", errors="replace")
            return text.split("\x00", 1)[0]
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


# ---------------------------------------------------------------- OCR 兜底（RapidOCR）

class OcrEngine:
    """RapidOCR(onnxruntime) 封装，延迟导入、缺库返回 None。识别数字表格用。"""

    def __init__(self):
        self._ocr = None
        self._err = None

    def _ensure(self):
        if self._ocr is None and self._err is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr = RapidOCR()
            except Exception as e:
                self._err = str(e)
        return self._ocr

    def available(self):
        return self._ensure() is not None

    def last_error(self):
        return self._err

    def recognize(self, pil_img):
        """整图识别 -> 文本行列表（按视觉从上到下）。失败返回 None。"""
        ocr = self._ensure()
        if ocr is None:
            return None
        try:
            import numpy as np
            result, _ = ocr(np.asarray(pil_img))
            if not result:
                return []
            boxes = [r[0] for r in result]
            texts = [str(r[1]) for r in result]
            rows = []
            for b, t in sorted(zip(boxes, texts),
                               key=lambda x: (round(min(p[1] for p in x[0]) / 15), min(p[0] for p in x[0]))):
                rows.append({"y": min(p[1] for p in b), "x": min(p[0] for p in b), "text": t})
            # 按行聚类（y 容差 15px）
            clustered = []
            for r in rows:
                line = next((ln for ln in clustered if abs(ln["y"] - r["y"]) <= 15), None)
                if line is None:
                    clustered.append({"y": r["y"], "cells": [r["text"]]})
                else:
                    line["cells"].append(r["text"])
            for ln in clustered:
                pass
            return sorted(clustered, key=lambda ln: ln["y"]) if clustered else None
        except Exception:
            return None

    def recognize_lines(self, pil_img):
        """识别并还原为文本行列表。"""
        res = self.recognize(pil_img)
        if res is None:
            return None
        return ["\t".join(ln["cells"]) for ln in res]


_OCR = OcrEngine()


def ocr():
    """全局 OCR 单例（延迟初始化）。"""
    return _OCR