# -*- coding: utf-8 -*-
"""第三路免费权威补充源，非界面操作 —— OpenVLab REST 采集器（openvlab_collector.py）。

来源：https://www.openvlab.cn/api/...（匿名 FastAPI，零登录零依赖）。

三个端点（全部匿名 GET，Accept: application/json）：
  1. /api/ctamap-all                    全品种波动率地图（83+ 品种 ATM IV/百分位/偏度/RV22/carry…）
  2. /api/dto/{code}                    单标的数据（最新价/bid/ask/vol/oi/涨跌…）
  3. /api/volatility-surface/{code}     按月期权曲面（行权价/C-P 持仓量/mktvol/T 型链）

依赖：urllib.request（零新依赖）、device_config、fusion。
产出：
  - quotes / option chains 写入 monitor.db（经 fusion 融合层）；
  - openvlab_surfaces/ 目录：按品种 JSON 快照供 dashboard 下钻展示；
  - 状态快照 openvlab 段 -> StatusHub -> dashboard.html。
"""
import json
import os
import time
from pathlib import Path

import device_config
import fusion

LOG = fusion.LOG
CONFIG = device_config.CONFIG
OV_CFG = CONFIG.get("openvlab") or {}
BASE = OV_CFG.get("base_url", "https://www.openvlab.cn")
TIMEOUT = OV_CFG.get("timeout", 15)
_GAP = OV_CFG.get("gap", 0.5)        # 请求间礼貌间隔（秒）
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (device collector)",
}


# ======================================================================
# 网络层
# ======================================================================

def _fetch(path):
    """GET BASE/path -> JSON（失败返回 None）。"""
    import urllib.request
    url = BASE.rstrip("/") + "/" + path.lstrip("/")
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status != 200:
                LOG.warning("openvlab HTTP %d: %s", resp.status, url)
                return None
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:
        LOG.warning("openvlab fetch 失败 %s: %s", path, exc)
        return None


# ======================================================================
# 纯函数解析器（零网络，离线可测）
# ======================================================================

def parse_ctamap_rows(rows):
    """ctamap-all 结果列表 -> 标准 dict 列表（跳过 prodUnd 为空的海外品种）。

    字段映射：
      product      -> code（小写主连，如 "EG_O" -> "eg"）
      product_alias -> variety（中文品种名）
      prodUnd      -> prod_und（主连代码，如 "EG"）
      exchange     -> exchange（交易所）
      price        -> price（最新价）
      atmv_current -> iv（ATM 隐含波动率 %）
      atmv_percentile -> iv_percentile（隐波历史百分位）
      atmv_1dchg   -> iv_1dchg（1 日变化）
      skew_current -> skew（偏度）
      skew_percentile -> skew_percentile
      ctn          -> ctn（carry / 持仓量变化率）
      frontfwd_mom -> frontfwd_mom（前月/远月动量）
    """
    out = []
    for item in rows or []:
        prod_und = (item.get("prodUnd") or "").strip()
        if not prod_und:
            continue
        code = (item.get("product") or prod_und).split("_")[0].lower()
        out.append({
            "code": code,
            "variety": (item.get("product_alias") or prod_und).strip(),
            "prod_und": prod_und,
            "exchange": (item.get("exchange") or "").strip(),
            "price": _f(item.get("price")),
            "iv": _f(item.get("atmv_current")),
            "iv_percentile": _f(item.get("atmv_percentile")),
            "iv_1dchg": _f(item.get("atmv_1dchg")),
            "skew": _f(item.get("skew_current")),
            "skew_percentile": _f(item.get("skew_percentile")),
            "ctn": _f(item.get("ctn")),
            "frontfwd_mom": _f(item.get("frontfwd_mom")),
            "source": "openvlab",
        })
    return out


def parse_dto_quote(data, code=""):
    """dto/{code} 响应 -> 单条行情 dict（取 instruments 列表首条），失败返回 None。

    预期结构：{"result": {"context": {"r": {"1d": 涨跌幅}, "i": {"s": [...], "i": [标的...]}}}}
    （兼容旧结构：context 直接挂在顶层时同样可解）
    标的字段：n(名称)、s(代码)、l(最新价)、p(昨收)、b(买价)、a(卖价)、v(成交量)、o(持仓量)
    """
    try:
        ctx = (data.get("result") or data).get("context") or {}
        instruments = (ctx.get("i") or {}).get("i") or []
        if not instruments:
            return None
        inst = instruments[0]
        price = inst.get("l")
        if price is None or float(price) <= 0:
            return None
        chg_1d = (ctx.get("r") or {}).get("1d")
        variety_name = inst.get("n") or ""
        inst_code = (inst.get("s") or code).lower()
        return {
            "variety": variety_name,
            "code": inst_code,
            "price": float(price),
            "bid": _f(inst.get("b")),
            "ask": _f(inst.get("a")),
            "volume": int(inst.get("v") or 0),
            "open_interest": int(inst.get("o") or 0),
            "chg_1d": _f(chg_1d),
            "source": "openvlab",
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (TypeError, ValueError, KeyError):
        return None


def parse_surface_legs(data, exp=None, code=""):
    """volatility-surface/{code} 响应 -> (calls, puts) 腿列表。

    data 结构：{"202610": {月: 持仓/Vol JSON}, "202701": {...}, ...}
    每月内：
      strike_poi_c     -> 行权价:call 持仓量 JSON str {"行权价": oi}
      strike_poi_p     -> 行权价:put  持仓量 JSON str
      mktvol_tday_call_bid -> [[行权价, vol], ...]（当日 call 隐波）

    返回格式：
      calls/puts = [{"strike": float, "oi": int, "code": str, "cp": "C"/"P"}]
      code 命名约定：品种2位小写 + YYMM(2+2) + C/P + 行权价，如 "sa2611C1060"
    """
    if not data or not isinstance(data, dict):
        return [], []

    # 选择到期月：指定 exp 或取第一个有数据的月份
    keys = sorted(data.keys())
    if not keys:
        return [], []
    exp = exp if exp and exp in data else next((k for k in keys if data.get(k)), keys[0])
    month_data = data.get(exp) or {}

    # 解析持仓量 JSON（字符串 -> dict）
    call_poi = _safe_json(month_data.get("strike_poi_c"))
    put_poi = _safe_json(month_data.get("strike_poi_p"))
    mktvol = _safe_json(month_data.get("mktvol_tday_call_bid")) or []

    # 构造到期月后缀：exp "202610" -> "2610"
    try:
        yymm = exp[-4:]  # 取后4位
    except (TypeError, ValueError):
        yymm = exp

    calls, puts = [], []

    # 按行权价遍历 call 持仓
    for strike_str, oi in (call_poi or {}).items():
        strike = _f(strike_str)
        if strike is None or strike <= 0:
            continue
        calls.append({
            "strike": strike,
            "oi": int(oi or 0),
            "code": "%s%sC%s" % (code.lower(), yymm, _fmt_strike(strike)),
            "cp": "C",
        })

    # 按行权价遍历 put 持仓
    for strike_str, oi in (put_poi or {}).items():
        strike = _f(strike_str)
        if strike is None or strike <= 0:
            continue
        puts.append({
            "strike": strike,
            "oi": int(oi or 0),
            "code": "%s%sP%s" % (code.lower(), yymm, _fmt_strike(strike)),
            "cp": "P",
        })

    calls.sort(key=lambda x: x["strike"])
    puts.sort(key=lambda x: x["strike"])
    return calls, puts


# ======================================================================
# 链组装（调 fusion.quant().option_chain.build_summary）
# ======================================================================

def _chain_legs_to_rows(calls, puts, sym, yy, mm, code=""):
    """calls/puts -> [(variety, chain_dict)] 供 fusion.ingest_option_chains。

    sym: 品种小写（如 "sa"）；yy, mm: 两位年/月（26, 10）。
    """
    if not calls or not puts:
        return None
    try:
        q = fusion.quant()
        chain = q["option_chain"].build_summary(sym, "", yy, mm, calls, puts)
        variety = code or sym.upper()
        return [(variety, chain)]
    except Exception as exc:
        LOG.debug("openvlab 链组装失败: %s", exc)
        return None


# ======================================================================
# 曲面快照落盘（供 dashboard 下钻展示）
# ======================================================================

def _surface_dir():
    """openvlab_surfaces/ 目录路径（在 data/ 下，按品种存储快照）。"""
    d = device_config.data_dir() / "openvlab_surfaces"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_surface_snapshot(code, data):
    """将 volatility-surface/{code} 原始响应写入 data/openvlab_surfaces/{code}.json。

    幂等：同品种同轮覆盖。返回文件路径字符串。
    """
    d = _surface_dir()
    fp = d / ("%s.json" % code.lower())
    blob = {
        "code": code.lower(),
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "surface": data or {},
    }
    fp.write_text(json.dumps(blob, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(fp)


def list_surface_snapshots():
    """扫描 data/openvlab_surfaces/*.json -> [{"code","ts","months":[str]}] 列表。

    用于 dashboard 下钻选择列表。
    """
    d = _surface_dir()
    out = []
    for fp in sorted(d.glob("*.json")):
        try:
            blob = json.loads(fp.read_text(encoding="utf-8"))
            months = sorted((blob.get("surface") or {}).keys())
            out.append({
                "code": blob.get("code", fp.stem),
                "ts": blob.get("ts", ""),
                "months": months,
                "path": str(fp),
            })
        except (json.JSONDecodeError, OSError):
            pass
    return out


def parse_surface_for_display(code, exp=None):
    """读快照 -> 展示用 dict：{"code","exp","months":[],"legs":[{"strike,c,call_oi,p,put_oi}]}

    用于 dashboard 按月展示曲面概览（无 T 型链，纯行权价-持仓量表格）。
    """
    fp = _surface_dir() / ("%s.json" % code.lower())
    if not fp.exists():
        return None
    try:
        blob = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    surface = blob.get("surface") or {}
    if not surface:
        return None
    months = sorted(surface.keys())
    exp = exp if exp and exp in surface else (months[0] if months else None)
    if not exp:
        return None
    month_data = surface[exp] or {}
    call_poi = _safe_json(month_data.get("strike_poi_c")) or {}
    put_poi = _safe_json(month_data.get("strike_poi_p")) or {}
    all_strikes = sorted(set(list(call_poi.keys()) + list(put_poi.keys())),
                         key=lambda x: _f(x) or 0)
    legs = []
    for s in all_strikes:
        strike = _f(s)
        if strike is None or strike <= 0:
            continue
        legs.append({
            "strike": strike,
            "call_oi": int(call_poi.get(s) or 0),
            "put_oi": int(put_poi.get(s) or 0),
        })
    total_call_oi = sum(x["call_oi"] for x in legs)
    total_put_oi = sum(x["put_oi"] for x in legs)
    return {
        "code": code.lower(),
        "exp": exp,
        "ts": blob.get("ts", ""),
        "months": months,
        "legs": legs,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "pcr_oi": round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else None,
    }


def parse_surface_chain_for_display(code, exp=None):
    """T 型链：读快照 -> {"code","exp","rows":[{"strike","c_code","c_oi","p_code","p_oi","vol"}]}

    用于 dashboard 行权价级 T 型链展示（同时显示 call / put 代码与持仓）。
    """
    fp = _surface_dir() / ("%s.json" % code.lower())
    if not fp.exists():
        return None
    try:
        blob = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    surface = blob.get("surface") or {}
    months = sorted(surface.keys())
    exp = exp if exp and exp in surface else (months[0] if months else None)
    if not exp:
        return None
    month_data = surface[exp] or {}
    call_poi = _safe_json(month_data.get("strike_poi_c")) or {}
    put_poi = _safe_json(month_data.get("strike_poi_p")) or {}
    mktvol = _safe_json(month_data.get("mktvol_tday_call_bid")) or []

    # 月后缀：exp "202610" -> "2610"
    yymm = exp[-4:] if len(exp) >= 4 else exp

    # vol 查找表：[[strike, vol], ...] -> {strike: vol}
    vol_map = {}
    for item in (mktvol or []):
        if item and len(item) >= 2:
            vol_map[str(item[0])] = _f(item[1])

    all_strikes = sorted(set(list(call_poi.keys()) + list(put_poi.keys())),
                         key=lambda x: _f(x) or 0)
    rows = []
    for s in all_strikes:
        strike = _f(s)
        if strike is None or strike <= 0:
            continue
        call_oi = int(call_poi.get(s) or 0)
        put_oi = int(put_poi.get(s) or 0)
        rows.append({
            "strike": strike,
            "c_code": "%s%sC%s" % (code.lower(), yymm, _fmt_strike(strike)),
            "c_oi": call_oi,
            "p_code": "%s%sP%s" % (code.lower(), yymm, _fmt_strike(strike)),
            "p_oi": put_oi,
            "vol": vol_map.get(str(s)),
        })
    return {
        "code": code.lower(),
        "exp": exp,
        "ts": blob.get("ts", ""),
        "rows": rows,
    }


# ======================================================================
# 冲突检测
# ======================================================================

def _conflict_check(openvlab_price, code, status=None):
    """openvlab 价格与 legend/ths 数据源对比：差异 > conflict_diff_pct 告警。

    返回 (ok, diff_pct)。ok=True 表示无冲突或无法比较。
    """
    try:
        if status is None:
            status = fusion.StatusHub()
        snapshot = status.snapshot()
    except Exception:
        return True, 0.0
    # 从 quotes 中找同 code 的 legend/ths 价格
    for q in snapshot.get("quotes") or []:
        if q.get("source") in ("legend_ui", "ths_ui") and q.get("code") == code:
            other_price = q.get("price")
            if other_price and float(other_price) > 0 and openvlab_price > 0:
                diff = abs(openvlab_price - float(other_price)) / float(other_price) * 100.0
                thr = CONFIG.get("quality", {}).get("conflict_diff_pct", 1.0)
                if diff > thr:
                    return False, round(diff, 2)
            break
    return True, 0.0


# ======================================================================
# 采集周期
# ======================================================================

def collect_cycle(status):
    """一轮采集：ctamap -> dto(主力合约) -> surface(主力合约) -> 冲突检测 -> 期权链写入。

    返回 {"ctamap": n, "quotes": n, "surfaces": n}。
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    result = {"ctamap": 0, "quotes": 0, "surfaces": 0}

    # --- 1. ctamap（全品种波动率地图）---
    ctamap_raw = _fetch("api/ctamap-all?add_overseas=true")
    ctamap_data = {}
    if ctamap_raw:
        rows = (ctamap_raw.get("result") or [])
        ctamap_data = parse_ctamap_rows(rows)
        result["ctamap"] = len(ctamap_data)

    # --- 2. dto（单标的数据）+ surface（按月曲面）—— 并行请求 ---
    codes_seen = set()
    quotes = []
    surfaces_data = {}

    # 收集需要请求的品种
    targets = []
    for item in ctamap_data:
        prod_und = item.get("prod_und", "")
        if not prod_und or prod_und.lower() in codes_seen:
            continue
        codes_seen.add(prod_und.lower())
        code_lower = prod_und.lower()

        # 冲突检测：ctamap 价格 vs legend/ths
        if item.get("price"):
            ok, diff = _conflict_check(item["price"], code_lower)
            if not ok:
                LOG.warning("openvlab 冲突告警 %s: 价格差异 %.2f%%（vs legend/ths）",
                            code_lower, diff)
                status.alert(code_lower, "openvlab 价格差异 %.2f%%" % diff)
        targets.append((prod_und, code_lower))

    # 并行请求 dto + surface
    from concurrent.futures import ThreadPoolExecutor, as_completed
    openvlab_cfg = CONFIG.get("openvlab", {})
    max_dto = openvlab_cfg.get("dto_limit", 30)
    max_surf = openvlab_cfg.get("surface_limit", 12)

    def _fetch_one(prod_und, code_lower):
        dto_result = None
        surf_result = None
        if len(quotes) < max_dto:
            try:
                dto_raw = _fetch("api/dto/%s" % prod_und)
                dto_result = parse_dto_quote(dto_raw, code=code_lower) if dto_raw else None
            except Exception as exc:
                LOG.debug("openvlab dto/%s 失败: %s", prod_und, exc)
        if len(surfaces_data) < max_surf:
            try:
                surf_raw = _fetch("api/volatility-surface/%s" % prod_und)
                if surf_raw and isinstance(surf_raw, dict):
                    surf_result = surf_raw.get("result", surf_raw)
            except Exception as exc:
                LOG.debug("openvlab surface/%s 失败: %s", prod_und, exc)
        return code_lower, dto_result, surf_result

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_one, p, c): (p, c) for p, c in targets}
        for fut in as_completed(futures):
            try:
                code_lower, dto_result, surf_result = fut.result()
                if dto_result:
                    quotes.append(dto_result)
                if surf_result:
                    surfaces_data[code_lower] = surf_result
            except Exception as exc:
                LOG.debug("openvlab 并行请求异常: %s", exc)

    # 写入 quotes 到 fusion（行情）
    if quotes:
        result["quotes"] = len(quotes)
        status.merge_quotes(quotes)
        # A2: openvlab 行情落 quotes 表（cycle=99 装置侧），供量化跨源校验
        try:
            fusion.ingest_quotes_batch(quotes, cycle=99, source="openvlab")
        except Exception as e:
            LOG.debug("openvlab quotes 落库失败: %s", e)

    # 写入期权链（cycle=0 覆盖式写入：先清再插）
    chain_rows = []
    for code_key, surf_data in surfaces_data.items():
        try:
            calls, puts = parse_surface_legs(surf_data, code=code_key)
            if calls and puts:
                sym = code_key
                # 取月份键 -> 解析 yy, mm
                months = sorted(surf_data.keys()) if isinstance(surf_data, dict) else []
                for exp in months:
                    try:
                        exp_int = int(exp)
                        yy = (exp_int // 100) % 100
                        mm = exp_int % 100
                        c2, p2 = parse_surface_legs(surf_data, exp=exp, code=code_key)
                        rows = _chain_legs_to_rows(c2, p2, sym, yy, mm, code=code_key)
                        if rows:
                            chain_rows.extend(rows)
                    except (ValueError, TypeError):
                        pass
        except Exception as exc:
            LOG.debug("openvlab 链组装 %s 失败: %s", code_key, exc)

    if chain_rows:
        fusion.ingest_option_chains(chain_rows, cycle=0, ts=ts)
        LOG.info("openvlab 期权链写入 %d 条", len(chain_rows))

    # 曲面快照落盘（供 dashboard 下钻）
    for code_key, surf_data in surfaces_data.items():
        try:
            save_surface_snapshot(code_key, surf_data)
            result["surfaces"] += 1
        except Exception as exc:
            LOG.debug("openvlab 快照落盘 %s 失败: %s", code_key, exc)

    # 状态：openvlab 面板
    surfaces_display = []
    for code_key in list(surfaces_data.keys())[:10]:
        sd = parse_surface_for_display(code_key)
        if sd:
            surfaces_display.append(sd)
    status.update(openvlab={
        "ctamap_count": result["ctamap"],
        "surfaces_count": result["surfaces"],
        "surfaces": surfaces_display,
        "ts": ts,
    })

    # 健康上报
    fusion.registry_record("openvlab", result["ctamap"] > 0,
                           "ctamap=%d quotes=%d surfaces=%d" % (
                               result["ctamap"], result["quotes"], result["surfaces"]))
    return result


# ======================================================================
# 探测 / 常驻循环
# ======================================================================

def probe(status=None, verbose=True):
    """--probe：探测 OpenVLab 三个匿名端点可达性。返回 True 表示可用。"""
    status = status or fusion.StatusHub()
    ok = True
    # ctamap-all
    try:
        raw = _fetch("api/ctamap-all?add_overseas=true")
        n = len(raw.get("result") or []) if raw else 0
        if verbose:
            print("[openvlab] ctamap-all: %d 品种 %s" % (n, "OK" if n > 0 else "空"))
        if n == 0:
            ok = False
    except Exception as exc:
        ok = False
        if verbose:
            print("[openvlab] ctamap-all 失败: %s" % exc)
    time.sleep(_GAP)
    # dto/{code}
    try:
        raw = _fetch("api/dto/SA")
        q = parse_dto_quote(raw, code="sa") if raw else None
        if verbose:
            print("[openvlab] dto/SA: %s" % ("OK (%s)" % q.get("variety") if q else "空"))
        if not q:
            ok = False
    except Exception as exc:
        ok = False
        if verbose:
            print("[openvlab] dto/SA 失败: %s" % exc)
    time.sleep(_GAP)
    # volatility-surface/{code}
    try:
        raw = _fetch("api/volatility-surface/SA")
        if raw:
            calls, puts = parse_surface_legs(raw, code="SA")
            if verbose:
                print("[openvlab] volatility-surface/SA: calls=%d puts=%d" % (len(calls), len(puts)))
        else:
            if verbose:
                print("[openvlab] volatility-surface/SA: 空")
            ok = False
    except Exception as exc:
        ok = False
        if verbose:
            print("[openvlab] volatility-surface/SA 失败: %s" % exc)
    status.software("openvlab", ok, "REST 匿名端点" if ok else "不可达")
    return ok


def loop(status, stop=None):
    """常驻循环：按 collect 间隔低频采集。"""
    from collector_base import run_collector_loop
    run_collector_loop("openvlab", collect_cycle, status, stop=stop,
                       intervals=CONFIG["intervals"])


# ======================================================================
# 内部工具
# ======================================================================

def _f(x):
    """安全 float 转换：None / 非数字 -> None。"""
    try:
        v = float(x)
        return v if v == v else None  # NaN -> None
    except (TypeError, ValueError):
        return None


def _safe_json(s):
    """JSON 字符串 -> Python 对象；失败返回 None。"""
    if not s or not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def _fmt_strike(strike):
    """行权价格式化：整数去小数点，保留有效数字。"""
    if strike == int(strike):
        return str(int(strike))
    return str(strike)
