# -*- coding: utf-8 -*-
"""Legend 全交互元素枚举：遍历左侧导航 + 每个页面所有可点击元素，建立界面地图。

用法: D:/Python/python.exe enum_ui.py
输出: ui_map/<序号>_<导航名>.txt
每页列出：
  - 所有 button（含文本/aria/title/class 摘要）
  - 所有 [role=tab] / [role=menuitem] / [role=checkbox] / [role=switch]
  - 所有 a 标签
  - 所有带 onClick 的 div/span（React 元素）
"""
import json
import os
import time
import urllib.request

import websocket

PORT = 9225
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "..", "01_Legend", "界面地图")
os.makedirs(OUT, exist_ok=True)

NAVS = ["市场", "行情", "波动率", "策略", "期货", "异动"]


def get_ws():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
        tabs = json.loads(r.read().decode("utf-8", "replace"))
    return [t for t in tabs if t.get("type") == "page"][0]["webSocketDebuggerUrl"]


def eval_js(expr):
    ws = websocket.create_connection(get_ws(), timeout=15, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": expr, "returnByValue": True}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                res = msg.get("result", {}).get("result", {})
                if res.get("exceptionDetails"):
                    return {"__error__": str(res["exceptionDetails"])[:200]}
                return res.get("value")
    finally:
        ws.close()


CLICKABLE_JS = r"""
(function(){
  var out = {buttons: [], tabs: [], links: [], clicks: [], inputs: [], checkboxes: []};
  function clean(t){ return (t||'').trim().replace(/\s+/g,' ').slice(0,60); }
  function cls(c){ return (typeof c==='string'&&c)?c.split(/\s+/).slice(0,4).join(' '):''; }
  function desc(el){
    return {text: clean(el.innerText||el.value||el.getAttribute('aria-label')||el.getAttribute('title')),
            aria: el.getAttribute('aria-label')||'',
            title: el.getAttribute('title')||'',
            cls: cls(el.className), role: el.getAttribute('role')||''};
  }
  document.querySelectorAll('button').forEach(function(b){ out.buttons.push(desc(b)); });
  document.querySelectorAll('[role=tab], [role=menuitem], [role=option], [role=checkbox], [role=switch], [role=radio]').forEach(function(el){
    out.tabs.push(desc(el));
  });
  document.querySelectorAll('a').forEach(function(a){ out.links.push({text: clean(a.innerText), href: (a.getAttribute('href')||'').slice(0,60)}); });
  document.querySelectorAll('input, select, textarea').forEach(function(el){
    out.inputs.push({type: el.type||el.tagName, ph: el.getAttribute('placeholder')||'', cls: cls(el.className)});
  });
  // 带 onclick 的非 button 元素（React 常见）
  document.querySelectorAll('[onclick]').forEach(function(el){
    if(el.tagName !== 'BUTTON') out.clicks.push(desc(el));
  });
  return out;
})();
"""


def click_nav(title):
    js = r"""
(function(){
  var btns = document.querySelectorAll('aside button');
  for (var i=0;i<btns.length;i++){
    var t = btns[i].getAttribute('title')||btns[i].getAttribute('aria-label')||'';
    if (t === %s) { btns[i].click(); return 'CLICKED'; }
  }
  return 'NOT_FOUND';
})();
""" % json.dumps(title)
    return eval_js(js)


def save(name, data):
    fn = os.path.join(OUT, name)
    with open(fn, "w", encoding="utf-8") as f:
        f.write("# %s\n\n" % name)
        f.write("## 按钮 (%d)\n" % len(data.get("buttons", [])))
        for i, b in enumerate(data.get("buttons", [])):
            f.write("[%03d] text=%r aria=%r title=%r role=%r cls=%r\n"
                    % (i, b.get("text"), b.get("aria"), b.get("title"), b.get("role"), b.get("cls")))
        f.write("\n## tab/menu/checkbox (%d)\n" % len(data.get("tabs", [])))
        for i, t in enumerate(data.get("tabs", [])):
            f.write("[%03d] text=%r aria=%r role=%r cls=%r\n"
                    % (i, t.get("text"), t.get("aria"), t.get("role"), t.get("cls")))
        f.write("\n## 链接 (%d)\n" % len(data.get("links", [])))
        for i, l in enumerate(data.get("links", [])):
            f.write("[%03d] text=%r href=%r\n" % (i, l.get("text"), l.get("href")))
        f.write("\n## 输入框 (%d)\n" % len(data.get("inputs", [])))
        for i, inp in enumerate(data.get("inputs", [])):
            f.write("[%03d] %r ph=%r cls=%r\n" % (i, inp.get("type"), inp.get("ph"), inp.get("cls")))
        f.write("\n## 其他 onclick 元素 (%d)\n" % len(data.get("clicks", [])))
        for i, c in enumerate(data.get("clicks", [])):
            f.write("[%03d] text=%r cls=%r\n" % (i, c.get("text"), c.get("cls")))
    print("saved", fn)


def main():
    # 当前页
    save("00_当前页.txt", eval_js(CLICKABLE_JS) or {})
    for i, nav in enumerate(NAVS, start=1):
        res = click_nav(nav)
        time.sleep(1.6)
        data = eval_js(CLICKABLE_JS) or {}
        data["_nav_click"] = res
        save("%02d_%s.txt" % (i, nav), data)
    print("done ->", OUT)


if __name__ == "__main__":
    main()
