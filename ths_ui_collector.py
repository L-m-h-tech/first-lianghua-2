# -*- coding: utf-8 -*-
"""同花顺期货通 界面业务采集器。

数据通道（按可读性自动降级）：
1. UIAutomation：定位"期货通"窗口 -> 读控件树/文本（自绘网格大概率空）；
2. 剪贴板：聚焦行情网格 -> Ctrl+A/Ctrl+C -> 解析制表符文本（easytrader 同款读法）；
3. 截图+OCR：前三者失效时对窗口截图，RapidOCR 识别数字表格；
4. 公告：Notice.xml（UTF-16，随时可读，无需登录）-> news 表。

不做任何登录/交易操作；软件由用户手动打开，装置只检测。
"""
import html
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import device_config
import fusion
from ui_collector import UiaAdapter, AdapterError, read_clipboard_text, parse_tsv, ocr

LOG = fusion.LOG
CONFIG = device_config.CONFIG
THS_CFG = CONFIG["ths"]


# ---------------------------------------------------------------- Notice.xml 解析（纯函数）

def _strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def parse_notice_xml(text):
    """Notice.xml 文本 -> {"last_login": [...], "notices": [{broker,date,content}]}。
    content 为 HTML 反转义去标签后的纯文本。"""
    out = {"last_login": [], "notices": []}
    if not text:
        return out
    out["last_login"] = re.findall(r"<LastLoginDate>(\d{8})</LastLoginDate>"
                                   r"<LastLoginAccount>([^<]+)</LastLoginAccount>", text)
    for broker_m in re.finditer(r"<BrokerNo>([^<]+)</BrokerNo>\s*<NoticeList>(.*?)</NoticeList>",
                                text, re.S):
        broker = broker_m.group(1).strip()
        for nm in re.finditer(r"<NoticeDate>(\d{8})</NoticeDate>\s*<Content>(.*?)</Content>",
                              broker_m.group(2), re.S):
            date = nm.group(1)
            content = _strip_html(html.unescape(nm.group(2)))
            if content:
                out["notices"].append({"broker": broker, "date": date, "content": content})
    return out


def recent_notices(parsed, days=7, now=None, max_per_day=3):
    """过滤近 days 天的公告（按 NoticeDate），每天最多 max_per_day 条，按日期倒序。"""
    now = now or datetime.now()
    cutoff = (now - timedelta(days=days)).strftime("%Y%m%d")
    items = []
    for n in parsed.get("notices") or []:
        d = n.get("date") or ""
        if d and d >= cutoff and d <= now.strftime("%Y%m%d"):
            items.append(n)
    items.sort(key=lambda x: x["date"], reverse=True)
    per_day = {}
    out = []
    for it in items:
        d = it["date"]
        if per_day.get(d, 0) >= max_per_day:
            continue
        per_day[d] = per_day.get(d, 0) + 1
        out.append(it)
    return out


def notices_to_news(notices, source="ths_notice"):
    """公告 dict 列表 -> news 行（insert_news 输入格式）。"""
    items = []
    for n in notices:
        date = n.get("date") or ""
        ts = "%s-%s-%s 09:00:00" % (date[:4], date[4:6], date[6:8]) if len(date) == 8 else None
        content = "[%s公告] %s" % (n.get("broker", "同花顺"), n.get("content", ""))
        items.append({"content": content, "source": source, "time": ts,
                      "important": 1, "confidence": 0.9})
    return items


def read_notice_file(path=None):
    """读 Notice.xml（UTF-16，自动兜底 BOM/缺 BOM）。"""
    path = path or THS_CFG.get("notice_xml")
    p = Path(path)
    if not p.exists():
        return None
    raw = p.read_bytes()
    if raw[:2] == b"\xff\xfe":
        return raw.decode("utf-16-le", errors="replace")
    if raw[:2] == b"\xfe\xff":
        return raw.decode("utf-16-be", errors="replace")
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- 行情采集（三级）

# OCR 降级路径的界面噪音关键词（标题栏/按钮/指标名，非行情行）
_OCR_NOISE_WORDS = (
    "自选", "盯盘", "快讯", "分时", "日线", "周线", "月线", "年线", "多周期", "个股资料",
    "盘口", "MACD", "成交量", "持仓量", "大单", "期转现", "分时九转", "分时均线",
    "明细", "简介", "价量", "基差", "社区", "资讯", "关联品种", "相关合约",
    "最新0.00", "均价0.00", "自定义", "套利", "外盘", "外汇", "股票", "环球",
    "交易", "加自选", "沪指", "同花顺商品", "期货通商品", "期货户", "股票户",
    "L2", "中金所", "名称↑",
    "序号", "代码", "现价", "名称", "涨幅", "主力", "绿就买", "自选板块",
    "多品种同列", "板块同列", "最近浏览", "组合", "2图", "4图", "6图", "9图",
    "期货通自选", "共有1只", "共有5只", "共有25只", "请选择", "ETF", "日线",
)


def is_quote_like(text):
    """OCR 文本行是否像行情行：含数字价格 + 不全是界面噪音。"""
    if not text:
        return False
    cells = [c.strip() for c in text.split("\t") if c.strip()]
    if len(cells) < 2:
        return False
    # 至少 2 个数字单元格（价格/涨跌/量）
    digit_cells = sum(1 for c in cells if re.fullmatch(r"[-+0-9.,%]+", c))
    if digit_cells < 2:
        return False
    # 第一列不应是纯界面噪音（含前缀匹配："共有N只代码" 变化形式）
    first = cells[0]
    if first in _OCR_NOISE_WORDS or any(w == first for w in _OCR_NOISE_WORDS):
        return False
    if first.startswith("共有") or first.startswith("请选择"):
        return False
    # 整行若全是噪音词（逐格判断）也丢弃
    noise_hits = sum(1 for c in cells if c in _OCR_NOISE_WORDS)
    if noise_hits >= len(cells):
        return False
    # 含品种名/合约代码才有效；纯数字/纯标点的行丢弃
    has_text = any(c for c in cells if re.search(r"[\u4e00-\u9fffA-Za-z]", c))
    if not has_text:
        return False
    # 含合约代码模式（大写+数字或小写+数字）才是行情行
    has_code = any(re.fullmatch(r"[A-Za-z]{1,4}\d{3,4}", c) for c in cells)
    if not has_code:
        # 没有代码但有中文+数字，也可能是行情（如只有"焦煤2701 1689.5 +2.7"无代码列）
        has_price_num = any(re.fullmatch(r"[-+]?[0-9][0-9.,]+", c) for c in cells
                           if len(c) >= 4 and "." in c)
        if not has_price_num:
            return False
    return True


def parse_quote_tsv(columns, row):
    """剪贴板行情行 -> 标准行情 dict（列名常识匹配，宽松解析）。"""
    def cell(*names):
        for i, c in enumerate(columns or []):
            if any(n in str(c) for n in names):
                return row[i] if i < len(row) else None
        return None

    price = cell("最新", "价格", "现价") or cell("买", "卖")
    if price is None:
        return None
    return {"variety": cell("名称", "品种") or "", "code": cell("合约", "代码") or "",
            "price": price, "chg_pct": cell("涨跌幅", "涨跌"),
            "volume": cell("成交量", "总量"), "open_interest": cell("持仓", "持仓量"),
            "bid": cell("买价", "买一"), "ask": cell("卖价", "卖一"),
            "source": "ths_ui", "ts": time.strftime("%Y-%m-%d %H:%M:%S")}


def parse_quote_ocr_row(row):
    """OCR 行情行（无列头，语义推断）-> 标准行情 dict。

    自选行情表典型行（OCR 错位导致列序不稳定）：
      序号 代码(小写/大写) 名称(中文) 现价 涨跌幅
      例: '3\tm2701\t豆粕2701\t3415\t+0.3'
          '白糖2701\t4\tSR2701\t5506\t+0.5'
    策略：正则识别合约代码；数字里排除序号(≤30整数)后取第一个为价格；
          名称取含中文的单元格。失败返回 None。
    """
    cells = [c.strip() for c in row if c.strip()]
    if len(cells) < 2:
        return None

    code = ""
    variety = ""
    nums = []
    for c in cells:
        m = re.fullmatch(r"[A-Za-z]{1,4}\d{3,4}", c)
        if m:
            code = code or c.upper()
            continue
        if re.fullmatch(r"[-+]?[0-9][0-9.,]*", c) and len(c) <= 14:
            nums.append(c)
            continue
        if re.search(r"[\u4e00-\u9fff]", c):
            # 名称（含中文），取第一个非噪音的
            if not variety and not c.startswith("序号"):
                variety = c

    if not code and not variety:
        return None
    # 排除序号（≤30 的整数且不带小数点）后的第一个数字作为价格
    price = None
    for c in nums:
        is_seq = re.fullmatch(r"[0-9]{1,2}", c) and int(c) <= 30
        if not is_seq:
            price = c
            break
    if price is None:
        return None
    chg = next((c for c in nums[nums.index(price) + 1:]
                if c.startswith(("+", "-")) or c.endswith("%")), None)
    vol_oi = [c for c in nums[nums.index(price) + 1:] if c != chg]
    # 清理 OCR 尾巴字符（"氧化铝2610色"/"豆粕2701动"/"苯乙烯2610网"）
    if variety:
        m = re.match(r"(.+?\d{3,4}).*$", variety)
        if m:
            variety = m.group(1)
    return {"variety": variety, "code": code, "price": price,
            "chg_pct": chg,
            "volume": vol_oi[0] if vol_oi else None,
            "open_interest": vol_oi[1] if len(vol_oi) > 1 else None,
            "source": "ths_ocr", "ts": time.strftime("%Y-%m-%d %H:%M:%S")}


def detect(status):
    """检测同花顺窗口/进程；返回 ("uia"|"offline", detail, adapter)。"""
    uia = UiaAdapter(name_re="期货通")
    if uia.connect(poll_sec=3):
        title = (uia.window.Name or "")[:40]
        # 窗口最小化/off-screen 时先恢复，否则截图与点击无效
        rect = uia.window.BoundingRectangle
        if rect.left < -1000 or rect.right - rect.left < 400:
            uia.window.SetActive()
            uia.window.SetTopmost(True)
            time.sleep(0.3)
            uia.window.SetTopmost(False)
            time.sleep(0.3)
        status.software("ths", True, title)
        return "uia", "窗口在线: %s" % title, uia
    status.software("ths", False, "未检测到同花顺期货通窗口")
    return "offline", "未检测到同花顺期货通", None


def _navigate_to_quote_tab(conn):
    """尝试切到"行情"Tab（AutomationId: Product.FuturePro.QuotationPage）。

    THS 窗口若最小化则先恢复（SetTopmost），再按 Name 找 TabItem 点击。
    """
    import uiautomation as auto
    try:
        # 确保窗口可见（非最小化/非 off-screen）
        rect = conn.window.BoundingRectangle
        if rect.right - rect.left < 400 or rect.left < -1000:
            conn.window.SetActive()
            conn.window.SetTopmost(True)
            time.sleep(0.3)
            conn.window.SetTopmost(False)
            time.sleep(0.3)
        # 直接遍历窗口子树找 TabItem
        for child1 in conn.window.GetChildren():
            for child2 in child1.GetChildren():
                if child2.ControlTypeName == "TabControl":
                    for child3 in child2.GetChildren():
                        name = child3.Name or ""
                        if "Quotation" in name:
                            child3.Click()
                            time.sleep(0.5)
                            return True
                        if "Favourite" in name:
                            # 如果自选tab，也点一下（它可能显示行情列表）
                            pass
    except Exception as e:
        LOG.debug("切换行情Tab失败: %s", e)
    return False


def probe(status=None, verbose=True):
    """--probe：窗口信息 + 控件树摸底 + 文本可读性结论。"""
    status = status or fusion.StatusHub()
    mode, detail, conn = detect(status)
    print("[同花顺] %s" % detail)
    if mode == "offline":
        print("  提示：请手动打开同花顺期货通（无需登录）后重试。")
        return mode
    print("  控件树（前 80 项）：")
    dump = (conn.dump_tree(max_depth=3, max_items=80) or "")
    print(dump[:4000] or "   (空——自绘界面，控件树无内容)")
    txt = conn.read_all_text()
    print("  可读文本行数: %d（自绘行情表格通常为 0）" % len([l for l in txt.splitlines() if l.strip()]))
    print("  建议：若上行为 0，走剪贴板(^A^C)或 OCR 通道（见 ths_ui_collector.collect_cycle）。")
    return mode


def _try_clipboard(status, conn, mapping=None):
    """聚焦行情网格 -> ^A^C -> 剪贴板文本 -> tsv 解析。返回 [行情 dict]。

    同花顺 FieldGrid 为自绘控件，^A^C 实际会触发键盘精灵输入框，
    剪贴板无法获取行情数据；保留接口仅为接口兼容，实际立即返回空。
    """
    return []


def _try_ocr(status, conn):
    """窗口截图 -> RapidOCR -> 行文本。返回识别到的文本行列表或 None。"""
    eng = ocr()
    if not eng.available():
        status.update(ocr={"available": False, "err": eng.last_error()})
        return None
    status.update(ocr={"available": True})
    shot = str(device_config.data_dir() / ("ths_ocr_%s.png" % time.strftime("%H%M%S")))
    conn.snapshot(shot)
    from PIL import Image
    try:
        lines = eng.recognize_lines(Image.open(shot))
    except Exception as e:
        LOG.debug("OCR 失败: %s", e)
        return None
    return lines


def collect_cycle(status, mapping=None):
    """一轮采集：公告必读；行情三级(控件树->剪贴板->OCR)尽力而为。"""
    result = {"notices": 0, "quotes": 0, "level": "offline"}
    try:
        parsed = parse_notice_xml(read_notice_file() or "")
        items = notices_to_news(recent_notices(parsed))
        result["notices"] = fusion.ingest_news(items, "ths_notice") if items else 0
        status.update(news_latest=[{"ts": it.get("time"), "content": it["content"][:60]}
                                   for it in items[:8]])
    except Exception as e:
        LOG.warning("公告读取失败: %s", e)

    mode, detail, conn = detect(status)
    if mode != "uia":
        fusion.registry_record("ths_ui", False)
        return result
    # 先尝试切到行情Tab，确保截图是报价表格而非K线图
    _navigate_to_quote_tab(conn)
    quotes = _try_clipboard(status, conn, mapping)
    level = "clipboard"
    if not quotes:
        lines = _try_ocr(status, conn)
        level = "ocr" if lines else "tree"
        if lines:
            rows = [t.split("\t") for t in lines
                    if is_quote_like(t)]
            quotes = []
            for row in rows[:80]:
                q = parse_quote_ocr_row(row)
                if q:
                    quotes.append(q)
            # 宽松兜底：能过滤但没解析成标准行的，也记录原始行（保证有输出）
            if not quotes:
                quotes = [{"variety": "", "code": t.split("\t")[0][:20], "price": t,
                           "source": "ths_ocr", "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
                          for t in lines[:80] if is_quote_like(t)]
    result["quotes"] = len(quotes)
    result["level"] = level
    if quotes:
        status.update(quotes=list(status.snapshot()["quotes"])[:20] +
                      [q for q in quotes[:20] if q.get("price")])
    fusion.registry_record("ths_ui", result["quotes"] > 0 or level == "ocr",
                           "level=%s quotes=%d" % (level, result["quotes"]))
    return result


def loop(status, stop=None):
    """常驻循环：公告每次都读；行情按 detect 结果调度。"""
    from collector_base import run_collector_loop
    run_collector_loop("ths", collect_cycle, status, stop=stop,
                       intervals=CONFIG["intervals"])