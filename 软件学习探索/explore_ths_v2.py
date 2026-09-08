# -*- coding: utf-8 -*-
"""同花顺期货通全面探索脚本：遍历12个主导航 + 5个次tab + 板块分类，记录每个页面的内容"""
import uiautomation as auto
import time
import json
import os
import base64

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "02_同花顺", "探索记录")
os.makedirs(OUT_DIR, exist_ok=True)

def find_ths_window():
    """找到同花顺期货通主窗口"""
    win = auto.WindowControl(Name="同花顺期货通", searchDepth=1)
    if not win.Exists(3):
        print("ERROR: 未找到同花顺期货通窗口")
        return None
    return win

def get_all_radios(win):
    """获取所有radio按钮"""
    radios = []
    for r in win.GetChildren():
        if r.ControlTypeName == "RadioButtonControl":
            name = r.Name or r.AutomationId or ""
            rect = r.BoundingRectangle
            radios.append({
                "name": name,
                "x": rect.left if rect else 0,
                "y": rect.top if rect else 0,
                "w": rect.width() if rect else 0,
                "h": rect.height() if rect else 0,
                "control": r
            })
    return radios

def get_all_tabs(win):
    """获取所有tab控件"""
    tabs = []
    for t in win.GetChildren():
        if t.ControlTypeName == "TabItemControl":
            name = t.Name or ""
            rect = t.BoundingRectangle
            tabs.append({
                "name": name,
                "x": rect.left if rect else 0,
                "y": rect.top if rect else 0,
                "control": t
            })
    return tabs

def get_page_text(win, max_chars=3000):
    """获取窗口内所有文本内容"""
    texts = []
    def collect_texts(ctrl, depth=0):
        if depth > 8:
            return
        try:
            name = ctrl.Name
            if name and len(name.strip()) > 0 and len(texts) < 200:
                texts.append(name.strip())
        except:
            pass
        try:
            for child in ctrl.GetChildren():
                collect_texts(child, depth+1)
        except:
            pass
    collect_texts(win)
    return "\n".join(texts[:200])

def click_radio_by_name(win, name, partial=False):
    """通过名称点击radio按钮"""
    for r in win.GetChildren():
        if r.ControlTypeName == "RadioButtonControl":
            rname = r.Name or ""
            if (partial and name in rname) or (rname == name):
                try:
                    r.Click()
                    print(f"  Clicked radio: {rname}")
                    return True
                except Exception as e:
                    print(f"  Click failed for {rname}: {e}")
                    return False
    print(f"  Radio '{name}' not found")
    return False

def click_tab_by_name(win, name):
    """通过名称点击tab"""
    for t in win.GetChildren():
        if t.ControlTypeName == "TabItemControl":
            tname = t.Name or ""
            if name in tname:
                try:
                    t.Click()
                    print(f"  Clicked tab: {tname}")
                    return True
                except Exception as e:
                    print(f"  Click failed for {tname}: {e}")
                    return False
    print(f"  Tab '{name}' not found")
    return False

def screenshot_window(win, filename):
    """截图保存"""
    try:
        import pyautogui
        rect = win.BoundingRectangle
        if rect:
            img = pyautogui.screenshot(region=(rect.left, rect.top, rect.width(), rect.height()))
            path = os.path.join(OUT_DIR, filename)
            img.save(path)
            print(f"  Screenshot: {filename}")
            return path
    except Exception as e:
        print(f"  Screenshot failed: {e}")
    return None

def main():
    print("=" * 60)
    print("同花顺期货通全面探索")
    print("=" * 60)
    
    win = find_ths_window()
    if not win:
        return
    
    # 获取窗口信息
    rect = win.BoundingRectangle
    print(f"窗口: {win.Name}, bounds=[{rect.left},{rect.top},{rect.left+rect.width()},{rect.top+rect.height()}]")
    
    results = {}
    
    # === 1. 探索顶部12个主导航 ===
    print("\n--- 顶部主导航 ---")
    main_tabs = [
        "自选", "合约", "期货", "期权", "套利", "外盘",
        "外汇", "股票", "环球", "资讯", "自定义", "交易"
    ]
    
    for tab_name in main_tabs:
        print(f"\n>>> 导航: {tab_name}")
        clicked = click_radio_by_name(win, tab_name)
        if not clicked:
            # 尝试partial match
            clicked = click_radio_by_name(win, tab_name, partial=True)
        time.sleep(2)
        
        # 获取页面文本
        text = get_page_text(win)
        results[tab_name] = {
            "clicked": clicked,
            "text_preview": text[:1500]
        }
        print(f"  文本预览({len(text)}字): {text[:300]}")
    
    # === 2. 回到自选页，探索5个次tab ===
    print("\n\n--- 次tab探索 ---")
    click_radio_by_name(win, "自选")
    time.sleep(1)
    
    sub_tabs = ["自选", "自选板块", "多品种同列", "板块同列", "最近浏览"]
    for tab_name in sub_tabs:
        print(f"\n>>> 次tab: {tab_name}")
        clicked = click_tab_by_name(win, tab_name)
        time.sleep(2)
        text = get_page_text(win)
        results[f"sub_{tab_name}"] = {
            "clicked": clicked,
            "text_preview": text[:1500]
        }
        print(f"  文本预览({len(text)}字): {text[:300]}")
    
    # === 3. 在自选板块页探索板块分类 ===
    print("\n\n--- 板块分类探索 ---")
    click_tab_by_name(win, "自选板块")
    time.sleep(1)
    
    board_cats = ["自选大全", "持仓期权", "能化", "能化期权", "农副", "农副期权",
                  "黑色", "黑色期权", "广期所"]
    for cat in board_cats:
        print(f"\n>>> 板块分类: {cat}")
        clicked = click_radio_by_name(win, cat)
        time.sleep(1.5)
        text = get_page_text(win)
        results[f"board_{cat}"] = {
            "clicked": clicked,
            "text_preview": text[:1000]
        }
        print(f"  文本预览({len(text)}字): {text[:200]}")
    
    # === 4. 保存结果 ===
    save_results = {}
    for k, v in results.items():
        save_results[k] = {
            "clicked": v["clicked"],
            "text_preview": v["text_preview"][:800]
        }
    
    with open(os.path.join(OUT_DIR, "探索结果.json"), "w", encoding="utf-8") as f:
        json.dump(save_results, f, ensure_ascii=False, indent=2)
    
    # 生成Markdown报告
    report = "# 同花顺期货通全面探索报告\n\n"
    report += f"> 探索时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    report += "## 顶部主导航\n\n"
    for tab_name in main_tabs:
        key = tab_name
        if key in results:
            r = results[key]
            report += f"### {tab_name}\n"
            report += f"- 点击成功: {'✅' if r['clicked'] else '❌'}\n"
            report += f"- 文本预览:\n```\n{r['text_preview'][:500]}\n```\n\n"
    
    report += "## 次tab\n\n"
    for tab_name in sub_tabs:
        key = f"sub_{tab_name}"
        if key in results:
            r = results[key]
            report += f"### {tab_name}\n"
            report += f"- 点击成功: {'✅' if r['clicked'] else '❌'}\n"
            report += f"- 文本预览:\n```\n{r['text_preview'][:500]}\n```\n\n"
    
    report += "## 板块分类\n\n"
    for cat in board_cats:
        key = f"board_{cat}"
        if key in results:
            r = results[key]
            report += f"### {cat}\n"
            report += f"- 点击成功: {'✅' if r['clicked'] else '❌'}\n"
            report += f"- 文本预览:\n```\n{r['text_preview'][:500]}\n```\n\n"
    
    with open(os.path.join(OUT_DIR, "探索报告.md"), "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n{'='*60}")
    print(f"探索完成！结果保存到: {OUT_DIR}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
