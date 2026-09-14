# -*- coding: utf-8 -*-
"""OpenVLab Legend 界面业务采集器。

模式（三级，按可用性自动降级）：
- CDP：探测 9225（或进程监听端口）-> 接入页面 -> 读 DOM 表格/点击/滚动 -> 解析融合；
- UIA：普通模式启动时，读窗口可读文本兜底（自绘内容读不到则报状态）；
- offline：软件未开/未就绪，仅记状态，不拉起软件。

实测节奏：selectors.json 的 legend_cdp 目前为空占位——先跑 `run.py --probe --legend`
枚举页面与表格候选，把确认的选择器与列映射固化进 selectors.json 后全功能生效。

只读不做任何下单/交易操作。
"""
import json
import re
import time
from datetime import datetime

import device_config
import fusion
from ui_collector import CdpAdapter, UiaAdapter, AdapterError

LOG = fusion.LOG
CONFIG = device_config.CONFIG
LEGEND_CFG = CONFIG["legend"]


# ---------------------------------------------------------------- 探测

def _probe_cdp():
    """找 Legend 的 CDP 调试口：优先配置端口，其次扫进程监听端口。"""
    cdps = CdpAdapter(LEGEND_CFG.get("cdp_port", 9225))
    if cdps.connect():
        return cdps
    # 进程端口探测（Legend 若自带调试口）
    ports = []
    try:
        found = __import__("ui_collector").find_process_ports(["openvlab"])
        for plist in found.values():
            ports.extend(plist)
    except Exception:
        pass
    ports = [p for p in ports if 8000 <= p <= 10000]
    if ports and cdps.connect(port_candidates=ports):
        return cdps
    return None


def detect(status):
    """返回 ("cdp"|"uia"|"offline", detail)。不拉起软件。"""
    cdps = _probe_cdp()
    if cdps is not None:
        pages = cdps.pages()
        detail = "CDP:%d 页面%d个" % (cdps.port, len(pages))
        status.software("legend", True, detail)
        return "cdp", detail, cdps
    uia = UiaAdapter(name_re=("Legend", "OpenVlab"))
    if uia.connect(poll_sec=3):
        status.software("legend", True, "UIA窗口可用(普通模式)")
        return "uia", "UIA窗口可用(普通模式，建议用调试bat以启用CDP)", uia
    status.software("legend", False, "未检测到 Legend（请手动打开）")
    return "offline", "未检测到 Legend", None


def _check_login(conn, status):
    """检测 Legend 登录态：若页面在 login-transition 则尝试自动重登。返回 True=正常。"""
    try:
        hash_val = conn.eval("window.location.hash")
        if "login" not in str(hash_val).lower():
            return True  # 未跳转到登录页
        LOG.info("Legend 登录态过期，尝试自动重登...")
        creds = device_config.legend_credentials()
        if not creds:
            LOG.warning("Legend 无可用凭据，需手动登录")
            return False
        # 尝试自动登录：填入账号密码并提交
        c = creds[0]
        uid = c.get("user_id", "")
        pwd = c.get("password", "")
        if not uid or not pwd:
            LOG.warning("Legend 凭据不完整（user_id=%s），需手动登录", uid)
            return False
        # CDP 填表提交
        js = f"""(function(){{
            var uidInput = document.querySelector('input[placeholder*="账号"], input[name*="user"], input[type="text"]');
            var pwdInput = document.querySelector('input[type="password"]');
            if (!uidInput || !pwdInput) return 'NO_INPUT';
            uidInput.value = {json.dumps(uid)};
            uidInput.dispatchEvent(new Event('input', {{bubbles:true}}));
            pwdInput.value = {json.dumps(pwd)};
            pwdInput.dispatchEvent(new Event('input', {{bubbles:true}}));
            var btn = document.querySelector('button[type="submit"], button:not([disabled])');
            if (btn) {{ btn.click(); return 'SUBMITTED'; }}
            return 'NO_BUTTON';
        }})()"""
        result = conn.eval(js)
        if "SUBMITTED" in str(result):
            LOG.info("Legend 自动登录已提交")
            time.sleep(3)  # 等待登录完成
            # 验证是否回到正常页面
            new_hash = conn.eval("window.location.hash")
            if "login" not in str(new_hash).lower():
                LOG.info("Legend 自动登录成功")
                return True
            LOG.warning("Legend 自动登录后仍在登录页，需手动操作")
            return False
        LOG.warning("Legend 自动登录: %s", result)
        return False
    except Exception as e:
        LOG.debug("Legend 登录检测异常: %s", e)
        return True  # 异常时不做判断，让后续采集正常尝试


def probe(status=None, verbose=True):
    """--probe：枚举页面/表格候选/UIA树，输出待固化的选择器。"""
    status = status or fusion.StatusHub()
    mode, detail, conn = detect(status)
    print("[Legend] 模式: %s — %s" % (mode, detail))
    if mode == "cdp":
        print("  CDP 端口: %d" % conn.port)
        for i, p in enumerate(conn.pages()[:20]):
            print("  [%d] %s | %s" % (i, p["title"][:30], p["url"][:60]))
        print("  页面表格候选（前 10 个）：")
        try:
            for i, c in enumerate(conn.select_probe()[:10]):
                print("  [%d] tag=%s 行数=%s 列=%s 首行=%s" %
                      (i, c.get("tag"), c.get("n"), c.get("cols"), c.get("first_row")))
        except Exception as e:
            print("  表格提取失败: %s" % e)
    elif mode == "uia":
        print("  UIA 控件树（前 60 项）：")
        print((conn.dump_tree(max_depth=3, max_items=60) or "")[:3000] or "  (空)")
    else:
        print("  提示：请手动启动 Legend 并登录模拟账号，或用『Legend 调试模式.bat』启动后重试。")
    return mode


# ---------------------------------------------------------------- 行情解析（列映射可配置）

def parse_quote_row(columns, row, mapping):
    """按 selectors 的 column_map 把界面一行解析为标准行情 dict。

    mapping: {目标字段: {"name": 列名子串} 或 {"idx": 列序号}}
    目标字段: variety/code/price/chg_pct/volume/open_interest/bid/ask
    返回 dict 或 None（关键字段缺失）。
    """
    def cell(field):
        spec = (mapping or {}).get(field)
        if not spec:
            return None
        if "idx" in spec:
            i = spec["idx"]
            return row[i] if 0 <= i < len(row) else None
        name = spec.get("name", "")
        for i, c in enumerate(columns or []):
            if name and name in str(c):
                return row[i] if i < len(row) else None
        return None

    price = cell("price")
    if price is None:
        return None
    out = {"variety": cell("variety") or "", "code": cell("code") or "",
           "price": price, "chg_pct": cell("chg_pct"),
           "volume": cell("volume"), "open_interest": cell("open_interest"),
           "bid": cell("bid"), "ask": cell("ask"), "source": "legend_ui",
           "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    return out


def clean_rows(table):
    """去掉全空行/表尾注脚行，返回 (columns, rows)。"""
    cols = table.get("columns") or []
    rows = []
    for r in table.get("rows") or []:
        if not any(str(c).strip() for c in r):
            continue
        rows.append(r)
    return cols, rows


# ---------------------------------------------------------------- 分钟聚合（先到先得写入）

class MinuteAggregator:
    """快照序列 -> 1 分钟 bar。每轮快照更新当前分钟 bar，跨分钟 flush。

    纯函数核心：aggregate(snap) -> (bar_dict or None, flushed_bar or None)
    """

    def __init__(self):
        self.bars = {}   # code -> {"minute","o","h","l","c","v","oi","period"}

    @staticmethod
    def _minute_key(ts=None):
        return (ts or time.strftime("%Y-%m-%d %H:%M")).rsplit(":", 1)[0]

    def aggregate(self, snap):
        """snap: parse_quote_row 产出。返回 (当前bar, 需要写入的bar)。"""
        code = snap.get("code") or snap.get("variety")
        if not code or snap.get("price") is None:
            return None, None
        cur = self.bars.get(code)
        minute = self._minute_key(snap.get("ts"))
        bar = {"sym": (snap.get("variety") or code).upper(), "contract": code,
               "exchange": "", "period": 1, "dt": minute + ":00",
               "trade_date": minute[:10],
               "o": float(snap["price"]), "h": float(snap["price"]),
               "l": float(snap["price"]), "c": float(snap["price"]),
               "v": float(snap.get("volume") or 0),
               "amount": 0.0, "src": snap.get("source", "legend_ui")}
        flush = None
        if cur is not None and cur["minute"] != minute:
            flush = {k: cur[k] for k in cur if k != "minute"}
            self.bars[code] = {"minute": minute, **bar}
        elif cur is not None:
            cur["h"] = max(cur["h"], bar["h"])
            cur["l"] = min(cur["l"], bar["l"])
            cur["c"] = bar["c"]
            cur["v"] = bar["v"]
            bar = cur
        else:
            self.bars[code] = {"minute": minute, **bar}
        return bar, flush

    def flush_all(self):
        """冲刷所有未跨分钟的当前 bar（--once 手动轮结束时调用）。
        返回 [bar, ...] 并清空内部状态；UNIQUE(contract,period,bar_dt)
        保证与跨分钟 flush 的先到先得去重一致。"""
        out = []
        for code, cur in list(self.bars.items()):
            out.append({k: cur[k] for k in cur if k != "minute"})
        self.bars.clear()
        return out


# ---------------------------------------------------------------- 期权链解析（复用 option_chain）

_LEG_RE = re.compile(r"^([a-z]+)(\d{4})([CP])(\d+\.?\d*)$", re.IGNORECASE)


def parse_option_leg(code, last=None, bid=None, ask=None, oi=None, chg_pct=None):
    """合约代码 -> 腿 dict（option_chain.parse_leg 输出格式，可直接进 build_summary）。"""
    m = _LEG_RE.match((code or "").strip())
    if not m:
        return None
    sym, yymm, cp, strike = m.group(1), m.group(2), m.group(3).upper(), m.group(4)
    return {"code": code, "cp": cp, "strike": float(strike),
            "bid_vol": 0, "bid": bid, "last": last, "ask": ask, "ask_vol": 0,
            "oi": oi, "chg_pct": chg_pct}


def build_chain_rows(leg_rows):
    """leg_rows: [腿 dict]（同品种同到期）-> 调 option_chain.build_summary 产出链摘要。
    返回 [(variety, chain)] 供 insert_option_chains。缺腿数据时返回 None。"""
    try:
        q = fusion.quant()
        calls = [l for l in leg_rows if l and l["cp"] == "C"]
        puts = [l for l in leg_rows if l and l["cp"] == "P"]
        if not calls or not puts:
            return None
        sym = (calls[0]["code"][:2].lower())
        m = _LEG_RE.match(calls[0]["code"])
        if not m:
            return None
        yy, mm = int(m.group(2)[:2]), int(m.group(2)[2:])
        chain = q["option_chain"].build_summary(sym, "", yy, mm, calls, puts)
        return [(sym.upper(), chain)]
    except Exception as e:
        LOG.debug("期权链组装失败: %s", e)
        return None


# A5: 期权链 cycle 约定——openvlab 固定 cycle=0，Legend 用 cycle=98，
# 避免两端同日链互相覆盖破坏 option_chains 的 PCR 历史分位。
LEGEND_CHAIN_CYCLE = 98


def ingest_legend_chains(chain_rows, ts=None):
    """Legend 期权链写库入口（cycle=98）。chain_rows 为 build_chain_rows 产出。"""
    if not chain_rows:
        return 0
    return fusion.ingest_option_chains(chain_rows, cycle=LEGEND_CHAIN_CYCLE, ts=ts)


# ---------------------------------------------------------------- 采集周期

def collect_cycle(status, agg=None, conn=None):
    """一轮采集：CDP 读行情表 -> 解析 -> 校验 -> 融合。返回 {"quotes": n, "bars": n}。"""
    if conn is None:
        mode, detail, conn = detect(status)
    else:
        # 第150轮：caller 已探测过时按 conn 类型判断 mode（原硬编码 "cdp" 导致
        # UIA 窗口模式下 conn 是 UiaAdapter，走 _collect_cdp 调 find_page 崩溃）
        mode = "cdp" if hasattr(conn, "find_page") else "uia"
    if mode == "cdp":
        r = _collect_cdp(status, conn, agg)
        # A4: --once 手动轮结束强制冲刷当前分钟 bar（跨分钟 flush 的补充）
        if agg is not None:
            orphan = agg.flush_all()
            if orphan:
                nb = fusion.ingest_minute_bars(orphan, "legend_ui")
                r["bars"] = r.get("bars", 0) + nb
        return r
    if mode == "uia":
        fusion.registry_record("legend_uia", True)
        return _collect_uia(status, conn)
    fusion.registry_record("legend_cdp", False)
    return {"quotes": 0, "bars": 0}


def _collect_cdp(status, conn, agg):
    if not _check_login(conn, status):
        fusion.registry_record("legend_cdp", False, "登录态异常")
        return {"quotes": 0, "bars": 0}
    sel = device_config.SELECTORS.get("legend_cdp") or {}
    url_kw = sel.get("page_url_kw") or sel.get("quote_page_url_kw") or "market"
    mapping = sel.get("column_map")
    conn.find_page(url_kw) or conn.open_url("https://www.openvlab.cn/market")
    table = conn.read_table(pick=sel.get("quote_table_pick", 0))
    cols, rows = clean_rows(table)
    if not rows:
        fusion.registry_record("legend_cdp", False, "无行")
        return {"quotes": 0, "bars": 0}
    quotes, bars = [], []
    for r in rows[:200]:
        snap = parse_quote_row(cols, r, mapping)
        if not snap or not snap.get("price"):
            continue
        ok, reason = fusion.check_price_jump(
            None if not quotes else quotes[-1].get("price"), snap["price"])
        ok2, reason2 = fusion.check_neg_spread(snap.get("bid"), snap.get("ask"))
        if not ok:
            fusion.alert_hub(status, snap.get("code") or "", reason)
        quotes.append(snap)
        b, fl = agg.aggregate(snap) if agg else (None, None)
        if fl:
            bars.append(fl)
    nq = len(quotes)
    # A2: Legend 行情落 quotes 表（cycle=99 装置侧），供量化跨源校验
    if nq:
        fusion.ingest_quotes_batch(quotes, cycle=99, source="legend_ui")
    nb = fusion.ingest_minute_bars(bars, "legend_ui") if bars else 0
    status.update(quotes=quotes[:80])
    fusion.registry_record("legend_cdp", nq > 0, "quotes=%d" % nq)
    return {"quotes": nq, "bars": nb}


def _collect_uia(status, conn):
    text = conn.read_all_text()
    conn.snapshot(str(device_config.data_dir() / ("legend_uia_%s.png" %
                                                  time.strftime("%H%M%S"))))
    fusion.registry_record("legend_uia", bool(text))
    return {"quotes": 0, "bars": 0, "uia_text_len": len(text)}


def loop(status, agg=None, stop=None):
    """常驻循环：探测就绪后按 collect 间隔采集；未就绪低频巡检。"""
    from collector_base import run_collector_loop
    _cached_conn = [None]

    def _detect_and_cache(status):
        mode, detail, conn = detect(status)
        _cached_conn[0] = conn if mode != "offline" else None
        return mode, detail, conn

    def _collect(status):
        return collect_cycle(status, agg, conn=_cached_conn[0])

    run_collector_loop("Legend", _collect, status, stop=stop,
                       intervals=CONFIG["intervals"], detect_fn=_detect_and_cache)