# -*- coding: utf-8 -*-
"""CDP 探索工具：通过 Chrome DevTools Protocol 认识/操作 OpenVlab Legend。

用法（Windows）：
  D:/Python/python.exe cdp_explore.py dump          # 导出页面可见文本（去重）
  D:/Python/python.exe cdp_explore.py menu          # 导出侧边栏/导航菜单结构
  D:/Python/python.exe cdp_explore.py tree          # 导出 DOM 关键节点树
  D:/Python/python.exe cdp_explore.py eval "<expr>" # 执行任意 JS 表达式
  D:/Python/python.exe cdp_explore.py click "<selector>"   # 点击匹配元素
  D:/Python/python.exe cdp_explore.py snap <png路径>        # 页面截图存文件

只读为主；点击/求值需要显式命令。本工具仅用于本地个人研究。
"""
import json
import re
import sys
import time
import urllib.request

import websocket

PORT = 9225
WS_TIMEOUT = 10


def get_tabs():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def find_page():
    tabs = [t for t in get_tabs() if t.get("type") == "page"]
    if not tabs:
        raise SystemExit("未找到页面 target")
    return tabs[0]


def eval_js(expr, timeout=WS_TIMEOUT):
    page = find_page()
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=timeout,
                                     suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": expr, "returnByValue": True}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                res = msg.get("result", {}).get("result", {})
                if res.get("exceptionDetails"):
                    return {"__error__": str(res["exceptionDetails"])[:300]}
                return res.get("value")
    finally:
        ws.close()


def cmd_dump():
    js = r"""
(function(){
  var out = [];
  var seen = new Set();
  function walk(el, depth){
    if(depth > 40) return;
    var kids = el.children || [];
    for(var i=0;i<kids.length;i++){
      var k = kids[i];
      var t = (k.innerText||'').trim();
      if(t && !seen.has(t)){ seen.add(t); out.push(t); }
      walk(k, depth+1);
    }
  }
  walk(document.body, 0);
  return out;
})();
"""
    vals = eval_js(js) or []
    print("=== 页面可见文本 (%d 条) ===" % len(vals))
    for i, v in enumerate(vals):
        line = v.replace("\n", " ⏎ ")[:200]
        print("[%03d] %s" % (i, line))


def cmd_menu():
    js = r"""
(function(){
  var out = [];
  // 常见侧边栏/导航容器选择器，尽量覆盖不同实现
  var sels = ['nav a','aside a','.menu a','.sidebar a','[class*=menu] a',
              '[class*=nav] a','[class*=tabs]','[class*=Tab]',
              'button[class*=menu]','button[class*=nav]','[role=tab]','[role=menuitem]'];
  var seen = new Set();
  sels.forEach(function(s){
    document.querySelectorAll(s).forEach(function(el){
      var t = (el.innerText||'').trim().replace(/\n+/g,' ');
      if(t && !seen.has(t)){ seen.add(t); out.push(t); }
    });
  });
  return out;
})();
"""
    vals = eval_js(js) or []
    print("=== 导航/菜单候选 (%d 条) ===" % len(vals))
    for i, v in enumerate(vals):
        print("[%03d] %s" % (i, v[:200]))


def cmd_tree():
    js = r"""
(function(){
  var lines = [];
  function tag(el, depth){
    var name = el.tagName ? el.tagName.toLowerCase() : '#text';
    var cls = (typeof el.className === 'string' && el.className)
        ? '.' + el.className.trim().split(/\s+/).join('.') : '';
    var id = el.id ? '#' + el.id : '';
    var txt = '';
    if (el.childNodes && el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
      txt = '="' + el.childNodes[0].nodeValue.trim().slice(0,20) + '"';
    }
    lines.push('  '.repeat(depth) + name + id + cls + txt);
    if(depth > 14) return;
    for (var i=0;i<el.children.length && i<120;i++) tag(el.children[i], depth+1);
  }
  tag(document.body, 0);
  return lines.slice(0, 900);
})();
"""
    vals = eval_js(js) or []
    print("=== DOM 节点树 (%d 行, 截断 900) ===" % len(vals))
    for line in vals:
        print(line[:220])


def cmd_eval(expr):
    res = eval_js(expr)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])


def cmd_click(selector):
    js = r"""
(function(){
  var el = document.querySelector(%s);
  if(!el) return 'NO_MATCH: ' + %s;
  el.scrollIntoView({block:'center'});
  el.click();
  return 'CLICKED ' + (el.innerText||'').trim().slice(0,50);
})();
""" % (json.dumps(selector), json.dumps(selector))
    print(eval_js(js))
    time.sleep(1.0)


def cmd_snap(path):
    js = r"""
(function(){
  var b = document.body;
  var w = b.scrollWidth || document.documentElement.scrollWidth;
  var h = b.scrollHeight || document.documentElement.scrollHeight;
  return {w:w, h:h, innerW: window.innerWidth, innerH: window.innerHeight};
})();
"""
    print("页面尺寸:", eval_js(js))
    page = find_page()
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20,
                                     suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Page.captureScreenshot",
                            "params": {"format": "png"}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                data = msg.get("result", {}).get("data")
                if not data:
                    print("截图失败:", str(msg)[:300])
                    return
                import base64
                with open(path, "wb") as f:
                    f.write(base64.b64decode(data))
                print("saved", path)
                return
    finally:
        ws.close()


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd = argv[0]
    if cmd == "dump":
        cmd_dump()
    elif cmd == "menu":
        cmd_menu()
    elif cmd == "tree":
        cmd_tree()
    elif cmd == "eval":
        cmd_eval(argv[1] if len(argv) > 1 else "location.href")
    elif cmd == "click":
        cmd_click(argv[1])
    elif cmd == "snap":
        cmd_snap(argv[1] if len(argv) > 1 else "cdp_shot.png")
    else:
        print("未知命令", cmd)


if __name__ == "__main__":
    main()
