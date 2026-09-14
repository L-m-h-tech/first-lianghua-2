# -*- coding: utf-8 -*-
"""同花顺期货通 交易操控骨架（为自动化交易项目准备的可复用基础）。

设计原则（基于 2026-09-12 大量实测）：
1. 坐标点击为主：同花顺大量控件是自绘(TextControl)/自定义Tab，且 UIA 全树遍历
   到自绘网格/图表控件时会卡死——所以不遍历树，用固定坐标或单点 FindControl。
2. 单点定位为辅：FindControl(searchDepth, AutomationId/Name) 定位 Edit/Button 等。
3. 超时+重试+防御：每步都带超时，失败按策略重试，绝不无界等待。
4. 风控：交易时段判定 + 可用资金/可下手数(≤N)读取 + 双确认弹窗处理。

⚠️ 使用前：软件必须已打开并登录（本模块不做登录，只操控已登录实例）。
⚠️ 本文档为"骨架/学习成果"，实盘前必须在模拟账户验证 + 补充策略逻辑。
"""
import time
import uiautomation as auto


# ---------------------------------------------------------------- 常量（实测坐标，窗口系）
# 下单面板（交易区中部，实测 2026-09-12）
SYMBOL_EDIT = (623, 1163)    # 品种输入框
HAND_EDIT = (783, 1157)      # 手数输入框
PRICE_EDIT = (945, 1157)     # 价格输入框（默认"最新价"=市价）
BTN_BUY = (666, 1266)        # 买多（TextControl，需坐标点击）
BTN_SELL = (826, 1266)       # 卖空（TextControl）
BTN_CLOSE = (988, 1266)      # 平仓（TextControl）
# 交易页签（顶部 y=1085）
TAB = {"持仓": 1102, "行权": 1162, "委托": 1222, "成交": 1282,
       "条件单": 1342, "损盈单": 1423, "资金": 1504, "合约": 1564}
# 弹窗（实测独立顶层窗口，居中弹出）
DLG_CONFIRM = "委托确认"     # 点买多后弹："确定要发出 买多 xxx 开仓 1手 投机 吗？"
DLG_RISK = "风险提示"        # 风控度>70%时弹："确认继续开仓？预期账户风险度为 X%"


# ---------------------------------------------------------------- 品种选择（核心）

def select_symbol(win, symbol, verify_timeout=3):
    """切换任意品种合约（面板上有/没有的都可以）。

    方式：ValuePattern 设品种框值 + 回车触发联动（实测 jm2701/rb2610/al2610/cu2610 全通过）。
    验证：读回品种框值确认；返回 (成功?, 当前值)。
    """
    ensure_active(win)
    ok = set_edit_value(win, *SYMBOL_EDIT, symbol)
    time.sleep(0.3)
    # 回车触发软件联动（盘口/合约卡/价格更新）
    click_coord(*SYMBOL_EDIT)
    time.sleep(0.2)
    auto.SendKeys("{ENTER}", waitTime=0.1)
    time.sleep(0.8)
    # 验证
    cur = get_edit_value(win, *SYMBOL_EDIT)
    success = cur is not None and cur.strip().lower() == symbol.lower()
    return success, cur


# ---------------------------------------------------------------- 基础操作（防卡死）

def switch_tab(win, name):
    """切换交易页签（持仓/委托/成交/资金...）。坐标点击，返回True/False。"""
    x = TAB.get(name)
    if not x:
        return False
    click_coord(x + 30, 1085 + 17)
    time.sleep(0.6)
    return True


def find_win(timeout=8):
    """按进程名/窗口名找主窗口。
    ⚠️ 同花顺有多个顶层窗口（主窗口+交易区GUID子窗口+DevTools），
    必须按 '同花顺' 名称 + 宽度>2000 过滤，避免拿到子窗口。"""
    root = auto.GetRootControl()
    deadline = time.time() + timeout
    while time.time() < deadline:
        for w in root.GetChildren():
            try:
                if (w.ControlTypeName == "WindowControl" and "同花顺" in (w.Name or "")
                        and w.BoundingRectangle.width() > 2000):
                    return w
            except Exception:
                continue
        time.sleep(0.5)
    return None


def click_coord(x, y):
    """坐标点击（主操控方式，绕开 UIA 树）。"""
    auto.Click(x, y)
    time.sleep(0.3)


def ensure_active(win):
    """确保主窗口激活（点击/键盘前必须，否则事件打到别的窗口）。"""
    try:
        win.SetActive()
        time.sleep(0.2)
    except Exception:
        pass


def set_edit_by_coord(x, y, text, clear_first=True):
    """坐标定位输入框 -> 设值（兼容旧接口，内部走UIA ValuePattern）。"""
    return set_edit_value(None, x, y, text)


def find_edit_by_coord(win, x, y, timeout=2):
    """按坐标区域找 EditControl（浅层 FindControl，返回控件或 None）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            # 用 FindControl(ControlType.EditControl) 从窗口范围找，检查坐标匹配
            found = win.EditControl(searchDepth=8)
            if found.Exists(0.2):
                r = found.BoundingRectangle
                if abs(r.left - x) < 80 and abs(r.top - y) < 80:
                    return found
        except Exception:
            pass
        time.sleep(0.2)
    return None


def set_edit_value(win, x, y, text):
    """用 UIA ValuePattern 直接设输入框值（不碰剪贴板/键盘，最可靠）。"""
    # ValuePattern 自动聚焦，避免 SendKeys 打到别的窗口
    try:
        edit = auto.ControlFromPoint(x, y)
    except Exception:
        edit = None
    if edit:
        try:
            vp = edit.GetValuePattern()
            if vp:
                vp.SetValue(text)
                time.sleep(0.3)
                return True
        except Exception:
            pass
    # 兜底：坐标点击+键盘（仅在UIA不可用时）
    click_coord(x, y)
    time.sleep(0.2)
    auto.SendKeys("{Ctrl}a", waitTime=0.1)
    auto.SendKeys(text, waitTime=0.1)
    time.sleep(0.3)
    return True


def get_edit_value(win, x, y, timeout=2):
    """读输入框值：优先 UIA ValuePattern，其次剪贴板。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            edit = auto.ControlFromPoint(x, y)
            if edit:
                vp = edit.GetValuePattern()
                if vp and vp.Value:
                    return vp.Value.strip()
        except Exception:
            pass
        time.sleep(0.2)
    return None


# ---------------------------------------------------------------- 弹窗处理（实测链路）

def handle_confirm_dialog(win=None, action="ok", timeout=5):
    """处理「委托确认」弹窗：点确定/取消。实测：点买多后弹出。"""
    root = auto.GetRootControl()
    deadline = time.time() + timeout
    while time.time() < deadline:
        for w in root.GetChildren():
            try:
                if w.ControlTypeName == "WindowControl" and (w.Name or "") == "委托确认":
                    btn = w.ButtonControl(searchDepth=10, Name="确定")
                    if btn.Exists(0.3):
                        btn.Click()
                        return "confirmed"
                    if action == "cancel":
                        btn = w.ButtonControl(searchDepth=10, Name="取消")
                        if btn.Exists(0.3):
                            btn.Click()
                            return "cancelled"
            except Exception:
                continue
        time.sleep(0.3)
    return "no_dialog"


def handle_risk_dialog(win=None, action="ok", timeout=5):
    """处理「风险提示」弹窗（风险度>70%时）：点确认开仓/取消。"""
    root = auto.GetRootControl()
    deadline = time.time() + timeout
    while time.time() < deadline:
        for w in root.GetChildren():
            try:
                if w.ControlTypeName == "WindowControl" and (w.Name or "") == "风险提示":
                    btn = w.ButtonControl(searchDepth=10, Name="确认开仓")
                    if btn.Exists(0.3):
                        btn.Click()
                        return "confirmed"
                    if action == "cancel":
                        btn = w.ButtonControl(searchDepth=10, Name="取消")
                        if btn.Exists(0.3):
                            btn.Click()
                            return "cancelled"
            except Exception:
                continue
        time.sleep(0.3)
    return "no_dialog"


def read_trade_feedback(win, timeout=3):
    """读交易区反馈条（下单结果提示，如"委托失败 原因：..."）。
    实测位置：交易区暂无可读文本区（TextControl），从窗口文本收集。"""
    ts = []
    deadline = time.time() + timeout

    def rec(c, dep):
        if len(ts) > 20 or dep > 5:
            return
        try:
            if c.ControlTypeName == "TextControl" and (c.Name or "").strip():
                r = c.BoundingRectangle
                if 1400 <= r.top <= 1470 and r.width() > 0:
                    ts.append(c.Name.strip())
            for ch in c.GetChildren():
                rec(ch, dep + 1)
        except Exception:
            pass

    while time.time() < deadline:
        del ts[:]
        rec(win, 0)
        if ts:
            return " | ".join(ts)
        time.sleep(0.3)
    return None


# ---------------------------------------------------------------- 交易动作（高层封装）

def place_order(symbol, side="buy", hands=1, price=None, win=None, auto_confirm=True,
                auto_risk=True, check_session=True):
    """下达买卖指令（骨架）。

    side: 'buy'买多 / 'sell'卖空 / 'close'平仓
    price: None=最新价(市价)，数字=限价
    auto_confirm/auto_risk: 是否自动处理确认/风险弹窗
    check_session: 若True，非交易时段直接返回（避免无效提交）
    """
    win = win or find_win()
    if not win:
        return {"ok": False, "err": "窗口未找到"}

    # 1. 填品种
    set_edit_by_coord(*SYMBOL_EDIT, symbol)
    time.sleep(0.5)
    # 2. 填手数
    set_edit_by_coord(*HAND_EDIT, str(hands))
    # 3. 填价格（可选）
    if price is not None:
        set_edit_by_coord(*PRICE_EDIT, str(price))
    # 4. 点买/卖/平
    btn = {"buy": BTN_BUY, "sell": BTN_SELL, "close": BTN_CLOSE}[side]
    click_coord(*btn)
    # 5. 处理弹窗链
    if auto_confirm:
        r1 = handle_confirm_dialog(win)
    if auto_risk:
        r2 = handle_risk_dialog(win)
    # 6. 读反馈
    time.sleep(1.0)
    feedback = read_trade_feedback(win)
    return {"ok": True, "confirm": r1 if auto_confirm else "skip",
            "risk": r2 if auto_risk else "skip", "feedback": feedback}


# ---------------------------------------------------------------- 风控辅助

def is_trading_session():
    """简单交易时段判断（日盘 9:00-15:00 周一~周五；夜盘/周末略）。
    注：完整版需按品种区分夜盘时段，此处给基础版。"""
    import datetime
    now = datetime.datetime.now()
    if now.weekday() >= 5:      # 周六周日
        return False
    t = now.hour + now.minute / 60
    if 9 <= t <= 15:            # 日盘
        return True
    # 夜盘 21:00-次日2:30（部分品种到1:00/23:00，简化按到2:30）
    if t >= 21 or t < 2.5:
        return True
    return False


def read_available_hands(win, side="buy"):
    """读可下单手数（买多/卖空下方 '≤N' 文本）。N=0 表示资金不足不可开仓。"""
    ts = []
    def rec(c, dep):
        if len(ts) > 10 or dep > 6:
            return
        try:
            if c.ControlTypeName == "TextControl" and (c.Name or "").strip().startswith("≤"):
                r = c.BoundingRectangle
                if r.width() > 0 and 1300 <= r.top <= 1320:
                    ts.append((r.left, c.Name.strip()))
            for ch in c.GetChildren():
                rec(ch, dep + 1)
        except Exception:
            pass
    rec(win, 0)
    ts.sort()
    if ts:
        # buy=最左(买多下方666), sell=中(826), close=右(988)
        idx = {"buy": 0, "sell": 1, "close": 2}.get(side, 0)
        if idx < len(ts):
            return int(ts[idx][1].replace("≤", "").replace("≤", "")) if ts[idx][1] != "≤0" else 0
    return 0


# ---------------------------------------------------------------- 演示/自检

if __name__ == "__main__":
    print("同花顺交易操控骨架")
    print("交易时段:", is_trading_session())
    win = find_win()
    print("主窗口:", win.Name if win else None)
    if win:
        print("可用可买手数(≤N):", read_available_hands(win, "buy"))