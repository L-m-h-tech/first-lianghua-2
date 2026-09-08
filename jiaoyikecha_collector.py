# -*- coding: utf-8 -*-
"""jiaoyikecha 交易可查 REST 数据源采集器（第四路：免费匿名基本面/持仓情绪补充源）。

数据源（www.jiaoyikecha.com，实测匿名可用；POST 表单 + URL 带 ?v=版本号）：
  会话三步：GET 首页 -> POST /ajax/session.php(响应 JSON 含 PHPSESSID) -> 带 cookie 调数据端点。
  端点（全部实测匿名 code=0）：
    daily_wr.php          仓单日报（76 品种）
    longhu_list.php       龙虎榜（10）
    niuxiong_list.php     牛熊榜（10）
    hg.php                支撑压力位（77，min3/min60 等部分字段 VIP 加密）
    broker_trend.php      席位大资金动向（70）
    net_position_list.php 席位净持仓（22，需 variety 参数）
    all_varieties.php     品种表（89，辅助索引）

用途：
  1. 仓单/龙虎/牛熊/支撑压力/席位资金/净持仓 -> device_jykc 快照表（幂等建表，
     量化侧零代码改动，按 item_type 只读消费）；
  2. 状态快照 jykc 段 -> dashboard 展示。
只读、低频（默认 sleep 0.5s）；仅个人研究用途。所有网络调用延迟导入（import 零依赖）。
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

import device_config
import fusion

LOG = fusion.LOG
CONFIG = device_config.CONFIG
JK_CFG = CONFIG.get("jiaoyikecha") or {}
BASE = JK_CFG.get("base_url", "https://www.jiaoyikecha.com")
TIMEOUT = JK_CFG.get("timeout", 20)
SLEEP = JK_CFG.get("sleep", 0.5)
VERSION = JK_CFG.get("version", "5f6760cc")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_ANON_OK = ("daily_wr", "longhu_list", "niuxiong_list", "hg",
            "broker_trend", "net_position_list", "all_varieties")


# ---------------------------------------------------------------- 网络层（延迟导入，失败降级）

class _JykcSession:
    """jiaoyikecha 匿名会话：三步流程取 PHPSESSID，POST 调端点。"""

    def __init__(self, timeout=TIMEOUT):
        import http.cookiejar
        self.timeout = timeout
        self.cookiejar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookiejar))
        self.opener.addheaders = [
            ("User-Agent", _UA),
            ("Accept", "application/json, text/javascript, */*; q=0.01"),
            ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
            ("Referer", BASE + "/www.jiaoyikecha.com"),
            ("X-Requested-With", "XMLHttpRequest"),
        ]

    def _ensure_session(self):
        if len(self.cookiejar) > 0:
            return
        # 1) 首页
        self.opener.open(BASE + "/www.jiaoyikecha.com", timeout=self.timeout)
        # 2) session.php 拿 PHPSESSID（接口把 cookie 放在 JSON 里，同时 Set-Cookie 也有）
        req = urllib.request.Request(
            BASE + "/ajax/session.php?v=" + VERSION, data=b"", method="POST")
        with self.opener.open(req, timeout=self.timeout) as r:
            body = r.read().decode("utf-8", "replace")
        try:
            d = json.loads(body)
            sid = (d.get("cookie") or {}).get("PHPSESSID")
        except Exception:
            sid = None
        # 若 Set-Cookie 没带上（urllib 已处理），手动注入
        if sid and not any(c.name == "PHPSESSID" for c in self.cookiejar):
            import http.cookiejar as hc
            c = hc.Cookie(0, "PHPSESSID", sid, None, False,
                          "www.jiaoyikecha.com", False, True, "/", True,
                          True, None, True, None, None, {})
            self.cookiejar.set_cookie(c)

    def post(self, endpoint, params=None):
        """POST /ajax/<endpoint>.php?v=... -> data（dict/list）；失败抛异常。"""
        self._ensure_session()
        body = urllib.parse.urlencode(params or {}).encode("utf-8")
        req = urllib.request.Request(
            BASE + "/ajax/%s.php?v=%s" % (endpoint, VERSION),
            data=body, method="POST")
        with self.opener.open(req, timeout=self.timeout) as r:
            raw = r.read().decode("utf-8", "replace")
        try:
            d = json.loads(raw)
        except Exception:
            raise ValueError("jiaoyikecha %s: 非 JSON 响应 %s" % (endpoint, raw[:120]))
        if d.get("code") not in (0,):
            raise ValueError("jiaoyikecha %s: %s" % (endpoint, d.get("msg")))
        return d.get("data")


def _get_session():
    """全局懒会话（失败即抛，调用方降级）。"""
    global _SESSION
    if _SESSION is None:
        _SESSION = _JykcSession()
    return _SESSION


_SESSION = None


# ---------------------------------------------------------------- 纯函数解析（离线可测）

def parse_warehouse_receipts(rows, date=None, ts=None):
    """daily_wr 仓单日报 -> 快照 dict 列表。

    rows: [{name, wr_unit, total_vol, total_chge, total_vol2, total_chge2, chge_rate}]
    返回 [{item_type:"wr", code:名称, variety:名称, data_date, value:{...}}]
    """
    date = date or time.strftime("%Y-%m-%d")
    out = []
    for r in rows or []:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "item_type": "wr", "code": name, "variety": name, "data_date": date,
            "value": {
                "total_vol": _to_float(r.get("total_vol")),
                "total_chge": _to_float(r.get("total_chge")),
                "total_vol2": _to_float(r.get("total_vol2")),
                "total_chge2": _to_float(r.get("total_chge2")),
                "chge_rate": _to_float(r.get("chge_rate")),
                "wr_unit": _to_float(r.get("wr_unit")),
            },
            "source": "jiaoyikecha",
        })
    return out


def parse_longhu(rows, date=None):
    """longhu_list 龙虎榜 -> [{item_type:"longhu", code, variety, value:{longhu}}]"""
    date = date or time.strftime("%Y-%m-%d")
    out = []
    for r in rows or []:
        code = (r.get("code") or "").strip()
        if not code:
            continue
        out.append({
            "item_type": "longhu", "code": code,
            "variety": (r.get("name") or code).strip(), "data_date": date,
            "value": {"longhu": _to_float(r.get("longhu"))},
            "source": "jiaoyikecha",
        })
    return out


def parse_niuxiong(rows, date=None):
    """niuxiong_list 牛熊榜 -> [{item_type:"niuxiong", code, variety, value:{niuxiong}}]"""
    date = date or time.strftime("%Y-%m-%d")
    out = []
    for r in rows or []:
        code = (r.get("code") or "").strip()
        if not code:
            continue
        out.append({
            "item_type": "niuxiong", "code": code,
            "variety": (r.get("name") or code).strip(), "data_date": date,
            "value": {"niuxiong": _to_float(r.get("niuxiong"))},
            "source": "jiaoyikecha",
        })
    return out


def parse_hg(rows, date=None):
    """hg 支撑压力位 -> [{item_type:"hg", code, variety, value:{current_price, time, min15}}]

    min15 为"偏多，支撑：16115-16145"这类中文文本（免费可见）；min3/min60 常为 VIP 加密 HTML。
    """
    date = date or time.strftime("%Y-%m-%d")
    out = []
    for r in rows or []:
        code = (r.get("code") or "").strip()
        if not code:
            continue
        out.append({
            "item_type": "hg", "code": code,
            "variety": (r.get("variety") or code).strip(), "data_date": date,
            "value": {
                "current_price": _to_float(r.get("current_price")),
                "time": (r.get("time") or "").strip(),
                "min15": _strip_html(r.get("min15")),
                "min3": _strip_html(r.get("min3")),
                "min60": _strip_html(r.get("min60")),
            },
            "source": "jiaoyikecha",
        })
    return out


def parse_broker_trend(rows, date=None):
    """broker_trend 席位大资金动向 -> [{item_type:"broker_trend", code:席位名, value:{...}}]"""
    date = date or time.strftime("%Y-%m-%d")
    out = []
    for r in rows or []:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "item_type": "broker_trend", "code": name, "variety": name, "data_date": date,
            "value": {
                "grade": (r.get("grade") or "").strip(),
                "money": _to_float(r.get("money")),
                "order_money": _to_float(r.get("order_money")),
                "variety": (r.get("variety") or "").strip(),
            },
            "source": "jiaoyikecha",
        })
    return out


def parse_net_positions(rows, variety="", date=None):
    """net_position_list 席位净持仓 -> [{item_type:"net_position", code:席位, variety, value:{...}}]"""
    date = date or time.strftime("%Y-%m-%d")
    out = []
    for r in rows or []:
        name = (r.get("broker") or "").strip()
        if not name:
            continue
        out.append({
            "item_type": "net_position", "code": name,
            "variety": (variety or "").strip(), "data_date": date,
            "value": {
                "net_position": _to_float(r.get("net_position")),
                "net_position_chge": _to_float(r.get("net_position_chge")),
            },
            "source": "jiaoyikecha",
        })
    return out


def parse_all_varieties(rows, date=None):
    """all_varieties 品种表 -> [{item_type:"variety", code:symbol, variety:name, value:{market}}]"""
    date = date or time.strftime("%Y-%m-%d")
    out = []
    for r in rows or []:
        sym = (r.get("symbol") or "").strip()
        if not sym:
            continue
        out.append({
            "item_type": "variety", "code": sym,
            "variety": (r.get("name") or sym).strip(), "data_date": date,
            "value": {"market": (r.get("market") or "").strip()},
            "source": "jiaoyikecha",
        })
    return out


def _to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _strip_html(s):
    import re
    if not s:
        return ""
    return re.sub(r"<[^>]+>", "", str(s)).strip()


# ---------------------------------------------------------------- 采集周期

def collect_cycle(status):
    """一轮采集：会话 + 各匿名端点 -> device_jykc 快照表 + 状态 jykc 段。

    返回 {"saved": n, "items": {端点: 条数}}。任一端点失败只记状态不中断。
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    date = time.strftime("%Y-%m-%d")
    stats = {}
    rows_all = []
    try:
        sess = _get_session()
    except Exception as e:
        LOG.warning("jiaoyikecha 会话失败: %s", e)
        status.source_hit("jiaoyikecha", False)
        return {"saved": 0, "items": {}, "error": str(e)[:100]}

    def _run(ep, parser, params=None, **kw):
        try:
            data = sess.post(ep, params)
            parsed = parser(data or [], **kw) if data else []
            stats[ep] = len(parsed)
            rows_all.extend(parsed)
            status.source_hit("jiaoyikecha_" + ep, True)
        except Exception as e:
            LOG.warning("jiaoyikecha %s 失败: %s", ep, e)
            status.source_hit("jiaoyikecha_" + ep, False)
            stats[ep] = 0
        finally:
            time.sleep(SLEEP)

    _run("all_varieties", parse_all_varieties, date=date)
    _run("daily_wr", parse_warehouse_receipts, date=date)
    _run("longhu_list", parse_longhu, date=date)
    _run("niuxiong_list", parse_niuxiong, date=date)
    _run("hg", parse_hg, date=date)
    _run("broker_trend", parse_broker_trend, date=date)
    # net_position_list：需逐品种请求，取主要品种
    for variety in ("螺纹钢", "热卷", "铁矿石", "焦煤", "焦炭",
                    "甲醇", "PTA", "纯碱", "原油", "豆粕"):
        _run("net_position_list", parse_net_positions,
             params={"variety": variety}, variety=variety, date=date)

    n_saved = 0
    if rows_all:
        n_saved = fusion.ingest_jykc_snapshots(rows_all, ts=ts)
    # 状态快照：dashboard 展示用摘要
    status.update(jykc=_status_summary(rows_all, date))
    fusion.registry_record("jiaoyikecha", n_saved > 0,
                           "saved=%d items=%s" % (n_saved, stats))
    return {"saved": n_saved, "items": stats}


def _status_summary(rows, date):
    """状态 jykc 段：按类型分组的最新数据（dashboard 直接展示）。"""
    by_type = {}
    for r in rows:
        by_type.setdefault(r["item_type"], []).append(r)
    out = {"date": date}
    for t, items in by_type.items():
        def _sort_key(x):
            val = (x.get("value") or {}).get(
                {"wr": "total_vol", "longhu": "longhu", "niuxiong": "niuxiong",
                 "hg": "current_price", "broker_trend": "money",
                 "net_position": "net_position", "variety": "market"}.get(t, ""), 0) or 0
            return -val if isinstance(val, (int, float)) else 0
        items = sorted(items, key=_sort_key)
        out[t] = items[:20]
    return out


def probe(status=None, verbose=True):
    """--probe：实测会话与匿名端点。"""
    status = status or fusion.StatusHub()
    ok = True
    try:
        sess = _get_session()
        data = sess.post("all_varieties")
        print("[jiaoyikecha] 会话+all_varieties: %d 品种 OK" % len(data or []))
        if data:
            print("  样例: %s %s (%s)" % (data[0].get("market"), data[0].get("name"),
                                          data[0].get("symbol")))
    except Exception as e:
        ok = False
        print("[jiaoyikecha] 会话/接口失败: %s" % e)
    for ep in ("daily_wr", "longhu_list", "niuxiong_list", "hg", "broker_trend"):
        try:
            data = sess.post(ep)
            print("[jiaoyikecha] %s: %d 条 OK" % (ep, len(data or [])))
        except Exception as e:
            ok = False
            print("[jiaoyikecha] %s 失败: %s" % (ep, e))
        time.sleep(SLEEP)
    status.software("jiaoyikecha", ok, "匿名 REST 端点")
    return ok


def loop(status, stop=None):
    """常驻循环：按 collect 间隔低频采集。"""
    from collector_base import run_collector_loop
    run_collector_loop("jiaoyikecha", collect_cycle, status, stop=stop,
                       intervals=CONFIG["intervals"])