# -*- coding: utf-8 -*-
"""同花顺期货通 期权交易操控模块（骨架，实测验证 2026-09-13）。

基于《学习手册》期权专章 + 实测结论：
- 期权代码格式：品种+月份-C/P-行权价（jm2610-C-1020 焦煤认购 / IO2612-P-3900 沪深300认沽）
- 期权下单面板：品种框/手数框/价格框（价格=权利金，可'市价'或限价数字）
- 下单弹窗链与期货一致：买多→委托确认→风险提示→柜台结果
- 期权特有：权利金+保证金双费用（合约卡显示），持仓表含希腊字母列
- 期权行情T型链：期权页（期权行情子视图）月份/认购认沽/实值虚值筛选

⚠️ 使用前：软件已登录；本模块不含策略逻辑，仅提供期权交易操控原语。
"""
import time
import uiautomation as auto
import sqlite3
import os

# 复用基础骨架
import ths_trade_control_skeleton as sk


# ---------------------------------------------------------------- 期权常量（实测坐标与期货一致）

OPTION_CODE_DB = r"E:\同花顺期货通\bin\data\code\code.db"


# ---------------------------------------------------------------- 期权代码工具

def parse_option_code(code):
    """解析期权代码 → dict：{variety, month, side, strike, subject}
    支持格式：jm2610-C-1020 / IO2612-P-3900 / ru2701C19250（无横杠容错）
    返回 None 表示不是期权代码。
    """
    import re
    code = code.strip()
    # 标准格式：品种+月份+-+C/P+-+行权价
    m = re.match(r"^([A-Za-z]{1,4})(\d{3,4})-([CP])-(\d+(?:\.\d+)?)$", code, re.I)
    if m:
        return {"variety": m.group(1), "month": m.group(2),
                "side": m.group(3).upper(), "strike": float(m.group(4))}
    # 无横杠格式：jm2610C1020
    m2 = re.match(r"^([A-Za-z]{1,4})(\d{3,4})([CP])(\d+(?:\.\d+)?)$", code, re.I)
    if m2:
        return {"variety": m2.group(1), "month": m2.group(2),
                "side": m2.group(3).upper(), "strike": float(m2.group(4))}
    return None


def normalize_option_code(code):
    """统一为界面格式：jm2610c1020 → jm2610-C-1020"""
    p = parse_option_code(code)
    if not p:
        return code
    return "%s%s-%s-%s" % (p["variety"], p["month"], p["side"], int(p["strike"]) if p["strike"] == int(p["strike"]) else p["strike"])


def query_option_db(code=None, variety=None, side=None, month=None):
    """从 code.db 查期权合约信息（离线字典）。
    返回 dict 或 list。字段：Code/Name/DisplayCode/ExprieDate/Subject/
    OptionSide/ExecutePrice/TradeAmount(乘数)/VarietyCode
    """
    if not os.path.exists(OPTION_CODE_DB):
        return None
    conn = sqlite3.connect(OPTION_CODE_DB)
    cur = conn.cursor()
    where = []
    args = []
    if code:
        where.append("DisplayCode=?"); args.append(normalize_option_code(code))
    if variety:
        where.append("VarietyCode=?"); args.append(variety)
    if side:
        where.append("OptionSide=?"); args.append("1" if side.upper() == "C" else "2")
    if month:
        where.append("DisplayCode LIKE ?"); args.append("%" + month + "%")
    sql = "SELECT * FROM Contracts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    cur.execute(sql, args)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    if code:
        return dict(zip(cols, rows[0])) if rows else None
    return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------- 期权下单

def switch_option_mode(win):
    """切到期权下单模式（radio '期权下单' x=851,y=1085）。"""
    r = win.RadioButtonControl(searchDepth=10, Name="期权下单")
    if r.Exists(0.5):
        r.Click()
    else:
        auto.Click(851 + 127, 1085 + 17)
    time.sleep(0.8)
    return True


def select_option(win, option_code):
    """选择期权合约（输入期权代码+回车联动）。
    option_code 支持 jm2610-C-1020 或 jm2610c1020，自动规范化为界面格式。
    返回 (成功?, 规范代码)。
    """
    norm = normalize_option_code(option_code)
    ok, cur = sk.select_symbol(win, norm)
    return ok, cur


def place_option_order(win, option_code, side="buy", hands=1, premium=None,
                       auto_confirm=True, auto_risk=True):
    """下达期权指令（骨架）。

    side: 'buy'买入开仓 / 'sell'卖出开仓 / 'close'平仓
    premium: None=市价；数字=限价权利金（如 700）
    实测：价格框可设'市价'或限价数字（ValuePattern.SetValue）
    """
    # 1. 切期权下单模式
    switch_option_mode(win)
    # 2. 选期权合约
    ok, cur = select_option(win, option_code)
    if not ok:
        return {"ok": False, "err": "期权合约选择失败: %s" % option_code}
    # 3. 手数
    sk.set_edit_value(win, *sk.HAND_EDIT, str(hands))
    # 4. 价格（权利金）
    if premium is not None:
        sk.set_edit_value(win, *sk.PRICE_EDIT, str(premium))
    # 5. 方向
    btn = {"buy": sk.BTN_BUY, "sell": sk.BTN_SELL, "close": sk.BTN_CLOSE}[side]
    sk.click_coord(*btn)
    # 6. 弹窗链
    r1 = sk.handle_confirm_dialog(win) if auto_confirm else "skip"
    r2 = sk.handle_risk_dialog(win) if auto_risk else "skip"
    time.sleep(1.0)
    return {"ok": True, "confirm": r1, "risk": r2,
            "symbol": cur, "premium": premium}


# ---------------------------------------------------------------- 期权行情

def read_option_chain(win):
    """读期权T型报价区文本（期权页，过滤HTML噪音）。
    返回列头+当前合约信息。"""
    ts = []
    def rec(c, dep):
        if len(ts) > 60 or dep > 6:
            return
        try:
            if c.ControlTypeName == "TextControl" and (c.Name or "").strip():
                r = c.BoundingRectangle
                nm = c.Name.strip()
                if r.width() > 0 and 150 <= r.top <= 800 and not any(
                        nm.startswith(k) for k in ("<", ">", "{", "}", "html", "DOCTYPE")):
                    ts.append((r.top, r.left, nm))
            for ch in c.GetChildren():
                rec(ch, dep + 1)
        except Exception:
            pass
    rec(win, 0)
    ts.sort()
    uniq = []
    for s in [x for _, _, x in ts]:
        if s not in uniq:
            uniq.append(s)
    return uniq


# ---------------------------------------------------------------- 演示/自检

if __name__ == "__main__":
    print("同花顺期权交易操控模块")
    # 代码解析测试
    for c in ["jm2610-C-1020", "jm2610c1020", "IO2612-P-3900", "rb2610"]:
        print("  %s -> %s -> %s" % (c, parse_option_code(c), normalize_option_code(c)))
    # 数据库查询测试
    info = query_option_db(code="jm2610-C-1020")
    if info:
        print("  jm2610-C-1020:", info.get("Name"), "到期", info.get("ExprieDate"),
              "标的", info.get("Subject"), "乘数", info.get("TradeAmount"))
    # 连接窗口
    win = sk.find_win()
    print("  主窗口:", win.Name if win else None)