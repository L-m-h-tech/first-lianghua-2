# -*- coding: utf-8 -*-
"""Legend 全元素地图提取器：把当前页所有可交互元素 + 文本块完整导出。

输出 JSON: {url, title, elements:[{type,tag,text,aria,title,rect}], texts:[...]}

用法:
  D:/Python/python.exe legend_map.py <out.json> [--all-frames]
"""
import json
import os
import sys
import urllib.request
import websocket

PORT = 9225
WS_TIMEOUT = 15


def get_ws():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
        tabs = json.loads(r.read().decode("utf-8", "replace"))
    page = [t for t in tabs if t.get("type") == "page"][0]
    return page["webSocketDebuggerUrl"]


def eval_js(expr, timeout=WS_TIMEOUT):
    ws = websocket.create_connection(get_ws(), timeout=timeout, suppress_origin=True)
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


JS = r"""
(function(){
  var out = {url: location.href, hash: location.hash, title: document.title,
             elements: [], texts: []};
  var SEEN = new Set();
  // 1) 所有按钮/链接/输入/下拉/开关/radio/tab/menuitem
  var sels = 'button,a,input,textarea,select,[role=tab],[role=menuitem],[role=radio],[role=switch],[role=checkbox]';
  document.querySelectorAll(sels).forEach(function(el){
    var r = el.getBoundingClientRect();
    if (r.width < 3 && r.height < 3) return;           // 跳过不可见
    if (r.bottom < 0 || r.right < 0) return;
    var text = (el.innerText || '').trim().replace(/\s+/g,' ').slice(0,80);
    var aria = el.getAttribute('aria-label') || '';
    var title = el.getAttribute('title') || '';
    var sp = el.getAttribute('data-state') || '';
    var cls = (typeof el.className === 'string' ? el.className : '').slice(0,70);
    var key = (el.tagName+'|'+text+'|'+aria+'|'+title);
    if (SEEN.has(key)) return;
    SEEN.add(key);
    out.elements.push({
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || '',
      text: text, arria: aria, title: title,
      state: sp, cls: cls,
      rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      visible: !!(el.offsetWidth || el.offsetHeight)
    });
  });
  // 2) 所有成块文本（叶子）
  var all = document.querySelectorAll('body *');
  for (var i=0;i<all.length;i++){
    var el = all[i];
    if (el.children.length > 0) continue;
    var t = (el.innerText || '').trim();
    if (t && t.length < 200) out.texts.push(t);
  }
  // 去重文本
  out.texts = out.texts.filter(function(v,i){ return out.texts.indexOf(v)===i; });
  return out;
})();
"""


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "legend_map.json"
    res = eval_js(JS)
    if res is None:
        print("NO DATA"); return
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("saved", out_path, "| elements:", len(res.get("elements", [])),
          "| texts:", len(res.get("texts", [])), "|", res.get("hash"))


if __name__ == "__main__":
    main()