# -*- coding: utf-8 -*-
"""自动遍历 Legend 左侧导航的每个页面，dump 内容存入 pages/ 目录。

用法: D:/Python/python.exe explore_nav.py
输出: pages/<序号>_<导航名>.txt   (页面可见文本 + 表格结构)
"""
import json
import os
import subprocess
import sys
import time

import websocket
import urllib.request

PORT = 9225
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "pages")
os.makedirs(OUT, exist_ok=True)

NAV_TITLES = ["市场", "行情", "波动率", "策略", "期货", "异动", "期权到期日历"]


def get_ws():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
        tabs = json.loads(r.read().decode("utf-8", "replace"))
    page = [t for t in tabs if t.get("type") == "page"][0]
    return page["webSocketDebuggerUrl"]


def eval_js(expr):
    ws = websocket.create_connection(get_ws(), timeout=10, suppress_origin=True)
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


def click_nav(title):
    js = r"""
(function(){
  var btns = document.querySelectorAll('aside button');
  for (var i=0;i<btns.length;i++){
    var t = btns[i].getAttribute('title')||'';
    if (t === %s) { btns[i].click(); return 'CLICKED ' + t; }
  }
  return 'NOT_FOUND ' + %s;
})();
""" % (json.dumps(title), json.dumps(title))
    return eval_js(js)


def dump_page_text():
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
    return eval_js(js) or []


def dump_tables():
    js = r"""
(function(){
  var out = [];
  document.querySelectorAll('table').forEach(function(t, ti){
    var rows = [];
    t.querySelectorAll('tr').forEach(function(tr){
      var cs = Array.from(tr.querySelectorAll('th,td')).map(function(c){return (c.innerText||'').trim();});
      if (cs.length) rows.push(cs);
    });
    out.push({table: ti, rows: rows.slice(0, 60)});
  });
  return out;
})();
"""
    return eval_js(js) or []


def save(name, title_click, texts, tables):
    fn = os.path.join(OUT, name)
    with open(fn, "w", encoding="utf-8") as f:
        f.write("## 导航: %s | 点击结果: %s\n\n" % (title_click, json.dumps(title_click, ensure_ascii=False)))
        f.write("### 可见文本 (%d 条)\n" % len(texts))
        for i, t in enumerate(texts):
            f.write("[%03d] %s\n" % (i, t.replace("\n", " ⏎ ")[:300]))
        f.write("\n### 表格 (%d 个)\n" % len(tables))
        for tb in tables:
            f.write("--- table %d ---\n" % tb["table"])
            for r in tb["rows"]:
                f.write(" | ".join(r) + "\n")
    print("saved", fn)


def main():
    # 先记录当前页面
    texts = dump_page_text()
    tables = dump_tables()
    save("00_当前页面_交易台.txt", "current", texts, tables)

    for i, title in enumerate(NAV_TITLES, start=1):
        try:
            res = click_nav(title)
            print("[%d] click %s -> %s" % (i, title, res))
            time.sleep(1.8)
            texts = dump_page_text()
            tables = dump_tables()
            save("%02d_%s.txt" % (i, title), res, texts, tables)
        except Exception as e:
            print("[%d] %s ERROR: %s" % (i, title, e))
            save("%02d_%s.txt" % (i, title), "ERROR " + str(e), [], [])
    print("done ->", OUT)


if __name__ == "__main__":
    main()
