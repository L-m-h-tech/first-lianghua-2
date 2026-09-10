# -*- coding: utf-8 -*-
"""协同层：连量化 monitor.db、复用其模块、质量校验、源打标、建新表。

- sys.path 注入量化目录，复用 storage.MonitorDB / option_chain / iv_surface / data_router；
- monitor.db 直连（SQLite WAL 多进程安全），分钟线走先到先得竞争写入；
- 新增 ctp_instruments 表（幂等 CREATE TABLE IF NOT EXISTS，不动现有表）；
- 质量护栏：跳变、负价差、断流检测（纯函数可测）+ 与量化库内价格冲突告警（读库，无网络）；
- REGISTRY 健康上报 + 状态快照收集，供 HTML 显示页使用。
"""
import importlib
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import device_config


# ---------------------------------------------------------------- 模块注入

_QUANT = None
_db = None


def setup_device_logger(name="device", file_name="device.log"):
    """装置独立日志：data/device.log（RotatingFile 风格简化版），调制与量化同款 LOG。"""
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fh = logging.FileHandler(device_config.data_dir() / file_name, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    log.addHandler(fh)
    log.propagate = False
    return log


LOG = setup_device_logger()


def ensure_quant():
    """注入量化目录并 import 其模块；失败抛 RuntimeError（融合层不可用）。"""
    global _QUANT
    if _QUANT:
        return _QUANT
    qdir = Path(device_config.quant_dir())
    if not (qdir / "storage.py").exists():
        raise RuntimeError("量化目录未找到: %s" % qdir)
    if str(qdir) not in sys.path:
        sys.path.insert(0, str(qdir))
    storage = importlib.import_module("storage")
    mconfig = importlib.import_module("config")
    option_chain = importlib.import_module("option_chain")
    iv_surface = importlib.import_module("iv_surface")
    data_router = importlib.import_module("data_router")
    _QUANT = {"storage": storage, "config": mconfig, "option_chain": option_chain,
              "iv_surface": iv_surface, "registry": data_router.REGISTRY}
    return _QUANT


def quant():
    return ensure_quant()


# ---------------------------------------------------------------- 数据库

def monitor_db():
    """量化侧 MonitorDB 实例（复用其建表/插口方法）。只建一次。"""
    global _db
    if _db is None:
        q = ensure_quant()
        db_path = q["config"].MONITOR_DB
        LOG.info("连接 monitor.db: %s", db_path)
        _db = q["storage"].MonitorDB(db_path)
        _ensure_ctp_instruments(_db)
    return _db


_CTP_SCHEMA = """
CREATE TABLE IF NOT EXISTS ctp_instruments(
    instrument_id TEXT PRIMARY KEY,
    product_id TEXT, exchange_id TEXT, product_class TEXT,
    options_type TEXT, volume_multiple REAL, price_tick REAL,
    instrument_name TEXT, trading_day TEXT, source TEXT,
    updated_real REAL
);
CREATE INDEX IF NOT EXISTS idx_ctp_product ON ctp_instruments(product_id);
"""

_JYKC_SCHEMA = """
CREATE TABLE IF NOT EXISTS device_jykc(
    item_type TEXT NOT NULL,
    code TEXT NOT NULL,
    variety TEXT,
    data_date TEXT NOT NULL,
    value_json TEXT,
    source TEXT,
    updated_real REAL,
    PRIMARY KEY(item_type, code, data_date)
);
CREATE INDEX IF NOT EXISTS idx_jykc_type ON device_jykc(item_type, data_date);
"""


def _ensure_ctp_instruments(db):
    with db.lock:
        db.conn.executescript(_CTP_SCHEMA)
        db.conn.commit()
        db.conn.executescript(_JYKC_SCHEMA)
        db.conn.commit()


def upsert_ctp_instruments(instruments, source="legend_cache"):
    """合约元数据 upsert：instruments 为 dict 列表（instrument_id 主键）。"""
    db = monitor_db()
    n = 0
    now = datetime.now().timestamp()
    with db.lock:
        for ins in instruments:
            iid = ins.get("instrument_id") or ins.get("instrumentId")
            if not iid:
                continue
            try:
                cur = db.conn.execute(
                    """INSERT OR REPLACE INTO ctp_instruments(instrument_id, product_id, exchange_id,
                       product_class, options_type, volume_multiple, price_tick, instrument_name,
                       trading_day, source, updated_real)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (iid,
                     ins.get("product_id") or ins.get("productId") or "",
                     ins.get("exchange_id") or ins.get("exchangeId") or "",
                     ins.get("product_class") or ins.get("productClass") or "",
                     ins.get("options_type") or ins.get("optionsType") or "",
                     float(ins.get("volume_multiple") or ins.get("volumeMultiple") or 0),
                     float(ins.get("price_tick") or ins.get("priceTick") or 0),
                     ins.get("instrument_name") or ins.get("instrumentName") or iid,
                     ins.get("trading_day") or ins.get("tradingDay") or "",
                     source, now))
                n += int(cur.rowcount or 0)
            except Exception as e:
                LOG.debug("ctp_instruments upsert 失败 %s: %s", iid, e)
        db.conn.commit()
    return n


def seed_ctp_instruments():
    """从量化 data/futures_margins.csv + futures_fees.csv 初始化 ctp_instruments。

    每品种写入一条 product 级元数据（volume_multiple 乘数 + exchange），
    instrument_id = 品种代码大写（如 RB），供 portfolio/paper_broker
    手数换算与保证金校准。幂等 seed，可重复调用。
    """
    try:
        q = ensure_quant()
        rows = []
        # margins: sym;name;exchange;broker_margin;exchange_margin;limit_basic;multiplier
        margin_csv = Path(q["config"].DATA_DIR) / "futures_margins.csv"
        if margin_csv.exists():
            for line in margin_csv.read_text(encoding="utf-8-sig").splitlines()[1:]:
                parts = line.split(",")
                if len(parts) < 7:
                    continue
                sym = (parts[0] or "").strip().upper()
                name = parts[1].strip()
                exch = parts[2].strip()
                try:
                    mult = float(parts[6])
                except (TypeError, ValueError):
                    mult = 0.0
                if sym and not rows or not any(r["instrument_id"] == sym for r in rows):
                    rows.append({"instrument_id": sym, "product_id": sym,
                                 "exchange_id": exch, "product_class": "future",
                                 "options_type": "", "volume_multiple": mult,
                                 "price_tick": 0.0, "instrument_name": name,
                                 "trading_day": "", "source": "seed_margins"})
        # fees: sym;name;exchange;account_flag;multiplier;...
        fee_csv = Path(q["config"].DATA_DIR) / "futures_fees.csv"
        if fee_csv.exists():
            for line in fee_csv.read_text(encoding="utf-8-sig").splitlines()[1:]:
                parts = line.split(",")
                if len(parts) < 5:
                    continue
                sym = (parts[0] or "").strip().upper()
                try:
                    mult = float(parts[4])
                except (TypeError, ValueError):
                    mult = 0.0
                r = next((x for x in rows if x["instrument_id"] == sym), None)
                if r:
                    if not r["volume_multiple"]:
                        r["volume_multiple"] = mult
                else:
                    rows.append({"instrument_id": sym, "product_id": sym,
                                 "exchange_id": "", "product_class": "future",
                                 "options_type": "", "volume_multiple": mult,
                                 "price_tick": 0.0, "instrument_name": sym,
                                 "trading_day": "", "source": "seed_fees"})
        if rows:
            return upsert_ctp_instruments(rows, source="seed")
        return 0
    except Exception as e:
        LOG.debug("ctp_instruments seed 失败: %s", e)
        return 0


def ingest_minute_bars(bars, source):
    """分钟线先到先得竞争写入（UNIQUE(contract,period,bar_dt) 由库保证）。返回新增行数。"""
    try:
        return monitor_db().insert_minute_bars(bars)
    except Exception as e:
        LOG.warning("分钟线写入失败: %s", e)
        return 0


def ingest_news(items, source):
    """公告/新闻写 news 表（content_hash 去重）。items: [{"content","source","time","important"}]"""
    try:
        return monitor_db().insert_news(items)
    except Exception as e:
        LOG.warning("news 写入失败: %s", e)
        return 0


def ingest_option_chains(chain_rows, cycle=None, ts=None):
    """期权链写 option_chains（PCR 历史分位）。chain_rows: [(variety_name, chain_dict)]"""
    try:
        return monitor_db().insert_option_chains(cycle or 0, ts or time.strftime("%Y-%m-%d %H:%M:%S"), chain_rows)
    except Exception as e:
        LOG.warning("option_chains 写入失败: %s", e)
        return 0


def clear_option_chains(cycle=0):
    """按 cycle 清空 option_chains 旧快照（openvlab 覆盖式写入前调用，收敛到融合层）。"""
    try:
        db = monitor_db()
        with db.lock:
            n = db.conn.execute("DELETE FROM option_chains WHERE cycle=?", (int(cycle),)).rowcount
            db.conn.commit()
        return n
    except Exception as e:
        LOG.warning("option_chains 清理失败: %s", e)
        return 0


_QUOTES_INSERT = """
INSERT INTO quotes(ts,cycle,variety,code,sym,exchange,cat,price,chg_pct,
                   open,high,low,prev_settle,volume,open_interest,created_real)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def ingest_quotes_batch(quotes, cycle=99, ts=None, source=None):
    """行情批量写 quotes 表（cycle=99 区分装置侧行情）。
    仅写入有有效价格的行；失败降级不阻塞。
    source: 数据源打标（legend_ui/ths_ui/openvlab），写入 cat 字段。"""
    if not quotes:
        return 0
    ts = ts or time.strftime("%Y-%m-%d %H:%M:%S")
    now = time.time()
    rows = []
    for q in quotes:
        try:
            price = float(q.get("price") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        code = str(q.get("code") or "")
        if not code:
            continue
        rows.append((ts, int(cycle), str(q.get("variety") or code), code,
                     str(q.get("sym") or ""), str(q.get("exchange") or ""),
                     str(source or q.get("cat") or "openvlab"),
                     price,
                     _safe_float(q.get("chg_pct")),
                     _safe_float(q.get("open")), _safe_float(q.get("high")),
                     _safe_float(q.get("low")), _safe_float(q.get("prev_settle")),
                     _safe_float(q.get("volume")), _safe_float(q.get("open_interest")),
                     now))
    if not rows:
        return 0
    try:
        db = monitor_db()
        with db.lock:
            db.conn.executemany(_QUOTES_INSERT, rows)
            db.conn.commit()
        return len(rows)
    except Exception as e:
        LOG.warning("quotes 批量写入失败: %s", e)
        return 0


def alert_hub(status, code, reason):
    """采集器质量告警入口：包装 StatusHub.alert()，status 为空时静默降级。

    原 legend_ui_collector 直接调用本函数；init 时 status 可能尚未就绪，
    因此这里做防御。返回 True 表示告警已记录。
    """
    try:
        if status is not None:
            status.alert(code, reason)
            return True
    except Exception as e:
        LOG.debug("alert_hub 记录失败: %s", e)
    return False


def _safe_float(v):
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def ingest_jykc_snapshots(items, ts=None):
    """jiaoyikecha 数据快照写入 device_jykc 表（幂等覆盖）。返回写入条数。"""
    if not items:
        return 0
    ts = ts or time.strftime("%Y-%m-%d %H:%M:%S")
    now = time.time()
    rows = []
    for it in items:
        iid = (it.get("code") or "").strip()
        if not iid:
            continue
        try:
            val = json.dumps(it.get("value") or {}, ensure_ascii=False)
        except Exception:
            val = "{}"
        rows.append((str(it.get("item_type") or ""), iid,
                     (it.get("variety") or iid).strip(),
                     str(it.get("data_date") or time.strftime("%Y-%m-%d")),
                     val, str(it.get("source") or "jiaoyikecha"), now))
    if not rows:
        return 0
    try:
        db = monitor_db()
        with db.lock:
            db.conn.executemany(
                """INSERT OR REPLACE INTO device_jykc
                   (item_type, code, variety, data_date, value_json, source, updated_real)
                   VALUES(?,?,?,?,?,?,?)""", rows)
            db.conn.commit()
        return len(rows)
    except Exception as e:
        LOG.warning("device_jykc 写入失败: %s", e)
        return 0


def registry_record(source, ok, detail=None):
    """上报数据源健康（量化 data_health 仪表盘）。"""
    try:
        quant()["registry"].record(source, ok)
    except Exception:
        pass


# ---------------------------------------------------------------- 质量护栏（纯函数）

def check_price_jump(prev, cur, threshold_pct=None):
    """价格跳变检测：返回 (ok, reason)。prev/cur 为价格或 None。"""
    if prev is None or cur is None:
        return True, ""
    if prev <= 0:
        return True, ""
    jump = abs(cur - prev) / prev * 100.0
    thr = threshold_pct or device_config.CONFIG["quality"]["max_price_jump_pct"]
    if jump > thr:
        return False, "价格跳变 %.2f%% > %.2f%%" % (jump, thr)
    return True, ""


def check_neg_spread(bid, ask):
    """负价差检测：买价>卖价（且两边都有效）视为脏数据。"""
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return True, ""
    if bid > ask:
        return False, "负价差 bid=%.2f ask=%.2f" % (bid, ask)
    return True, ""


def staleness_seconds(ts, now=None):
    """距 now 的秒数（ts 为字符时间或 epoch）。用于断流检测。"""
    if not ts:
        return None
    now = now or time.time()
    if isinstance(ts, (int, float)):
        return now - ts
    try:
        dt = datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
        return now - dt.timestamp()
    except (TypeError, ValueError):
        return None


def conflict_with_db(code, price, threshold_pct=None):
    """与量化库内最近一条同 code 报价对比：返回 (ok, diff_pct, db_price)。读库、无网络。"""
    thr = threshold_pct or device_config.CONFIG["quality"]["conflict_diff_pct"]
    try:
        db = monitor_db()
        with db.lock:
            row = db.conn.execute(
                "SELECT price, ts FROM quotes WHERE code=? ORDER BY created_real DESC LIMIT 1",
                (str(code),)).fetchone()
        if not row or not row["price"]:
            return True, 0.0, None
        db_price = float(row["price"])
        if db_price <= 0 or price is None or price <= 0:
            return True, 0.0, db_price
        diff = abs(price - db_price) / db_price * 100.0
        return (diff <= thr), diff, db_price
    except Exception:
        return True, 0.0, None


# ---------------------------------------------------------------- 状态快照（供 HTML 页）

class StatusHub:
    """跨线程收集装置状态，统一写 data/collector_status.json，供 dashboard 读取。"""

    def __init__(self, path=None):
        self.path = Path(path) if path else device_config.status_file()
        self.cache = {
            "updated": None, "collections": 0,
            "software": {},      # legend/ths: {"online": bool, "last_ok": ts, "detail": ""}
            "sources": {},       # source_name: {"ok": bool, "hits": int, "last": ts}
            "quotes": [],        # 最新行情快照 [{code, variety, price, chg, vol, oi, source}]
            "options": [],       # 期权链摘要 [{sym, expiry, pcr, atm_iv, source}]
            "alerts": [],        # 质量告警 [{ts, code, reason}]
            "news_latest": [],   # 最近公告 [{ts, content}]
            "coverage": {},      # minute_bars 覆盖
            "ocr": {"available": False},
        }
        self._lock = __import__("threading").RLock()

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self.cache, ensure_ascii=False))

    def update(self, **kw):
        with self._lock:
            self.cache.update(kw)
            self.cache["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def increment(self, key, delta=1):
        with self._lock:
            self.cache[key] = self.cache.get(key, 0) + delta

    def merge_quotes(self, new_quotes, max_len=80):
        with self._lock:
            old = self.cache.get("quotes") or []
            self.cache["quotes"] = old[-max_len:] + new_quotes[:max_len]

    def touch(self, cache, **kw):
        with self._lock:
            cache.update(kw)

    def software(self, name, online, detail=""):
        with self._lock:
            self.cache["software"][name] = {
                "online": bool(online), "last_ok": time.strftime("%H:%M:%S"), "detail": detail}

    def source_hit(self, name, ok=True):
        with self._lock:
            s = self.cache["sources"].setdefault(name, {"hits": 0, "ok": True, "last": ""})
            s["hits"] += 1
            s["ok"] = bool(ok)
            s["last"] = time.strftime("%H:%M:%S")

    def alert(self, code, reason):
        with self._lock:
            if len(self.cache["alerts"]) > 100:
                self.cache["alerts"] = self.cache["alerts"][-50:]
            self.cache["alerts"].append({"ts": time.strftime("%H:%M:%S"),
                                         "code": str(code), "reason": reason})

    def save(self):
        self.path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=1),
                             encoding="utf-8")

    def load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def report_json(self):
        """量化报告可消费的紧凑状态。"""
        snap = self.snapshot()
        software = {k: {"online": v.get("online", False), "detail": v.get("detail", "")}
                    for k, v in (snap.get("software") or {}).items()}
        sources = {k: {"ok": v.get("ok", False), "hits": v.get("hits", 0)}
                   for k, v in (snap.get("sources") or {}).items()}
        quotes = snap.get("quotes") or []
        by_src = {}
        for q in quotes:
            s = q.get("source", "?")
            by_src.setdefault(s, []).append(q)
        return {"updated": snap.get("updated"),
                "collections": snap.get("collections", 0),
                "software": software, "sources": sources,
                "quotes_total": len(quotes),
                "quotes_by_source": {k: len(v) for k, v in by_src.items()},
                "options": snap.get("options") or [],
                "alerts": (snap.get("alerts") or [])[-10:],
                "news_latest": (snap.get("news_latest") or [])[:5],
                "coverage": snap.get("coverage") or {},
                "ocr_available": bool((snap.get("ocr") or {}).get("available"))}

    def save_report(self, path=None):
        """写 data/report_device.json + 量化侧 reports/device_status.txt。"""
        from pathlib import Path
        p = Path(path) if path else (device_config.data_dir() / "report_device.json")
        p.write_text(json.dumps(self.report_json(), ensure_ascii=False, indent=1),
                     encoding="utf-8")
        try:
            qdir = Path(device_config.quant_dir())
            txt = qdir / "reports" / "device_status.txt"
            txt.write_text(self._device_status_text(), encoding="utf-8")
        except Exception as e:
            LOG.debug("device_status.txt 写入失败: %s", e)
        return str(p)

    def _device_status_text(self):
        """人类可读装置状态块。"""
        s = self.snapshot()
        lines = [
            "数据采集装置（界面操作）状态", "=" * 40,
            "最近更新: %s | 采集轮数: %s" % (s.get("updated"), s.get("collections")), "",
            "软件在线:"]
        for k, v in (s.get("software") or {}).items():
            lines.append("  %-12s %s  %s" % (k, "在线" if v.get("online") else "离线",
                                             v.get("detail") or ""))
        lines.append("")
        lines.append("数据源: %s" % ((s.get("sources") and sorted(s["sources"])) or "无"))
        qs = s.get("quotes") or []
        if qs:
            by = {}
            for q in qs:
                by[q.get("source")] = by.get(q.get("source"), 0) + 1
            lines.append("行情快照: %d 条 | 按源: %s" % (len(qs), by))
        opts = s.get("options") or []
        if opts:
            lines.append("期权链: %d 条" % len(opts))
        jk = s.get("jykc") or {}
        if jk:
            jk_n = " ".join("%s=%d" % (k, len(v)) for k, v in jk.items() if isinstance(v, list))
            lines.append("jiaoyikecha 快照(%s): %s" % (jk.get("date"), jk_n))
        alerts = s.get("alerts") or []
        if alerts:
            lines.append("")
            lines.append("最近质量告警 (%d):" % len(alerts))
            for a in alerts[-5:]:
                lines.append("  [%s] %s: %s" % (a.get("ts"), a.get("code"), a.get("reason")))
        lines.append("")
        lines.append("（由界面操作收集装置写入，实时刷新）")
        return "\n".join(lines) + "\n"


def latest_coverage():
    """minute_bars/option_chains 最近覆盖（读库，供 HTML 页）。"""
    try:
        db = monitor_db()
        cov = db.minute_bars_coverage()
        with db.lock:
            oc = db.conn.execute(
                "SELECT COUNT(*) AS n, MAX(ts) AS last, MIN(ts) AS first FROM option_chains"
            ).fetchone()
        cov["option_chains"] = {"rows": oc["n"], "last": oc["last"], "first": oc["first"]} if oc else {}
        return cov
    except Exception as e:
        LOG.debug("coverage 读取失败: %s", e)
        return {}