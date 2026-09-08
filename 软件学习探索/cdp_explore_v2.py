"""Legend CDP 深度探索工具 v2"""
import json, sys, time
try:
    import websocket
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'websocket-client', '-q'])
    import websocket

WS_URL = "ws://127.0.0.1:9225/devtools/page/A02AD43D3C825DE779E5E1DF24F560F3"

def send_cmd(ws, method, params=None, mid=None):
    if mid is None:
        mid = int(time.time()*1000) % 1000000
    msg = {"id": mid, "method": method}
    if params: msg["params"] = params
    ws.send(json.dumps(msg))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == mid:
            return resp
        # skip events
        if mid == 0:
            return resp

def main():
    cmd = sys.argv[1] if len(sys.argv)>1 else "dump"
    ws = websocket.create_connection(WS_URL, timeout=10, suppress_origin=True)
    
    if cmd == "dump":
        # Get full page text content
        r = send_cmd(ws, "Runtime.evaluate", {
            "expression": """
                (() => {
                    // Get sidebar navigation items
                    const sidebar = document.querySelector('aside') || document.querySelector('nav');
                    const navItems = Array.from(document.querySelectorAll('aside button[aria-label], nav button[aria-label]'))
                        .map(b => b.getAttribute('aria-label'));
                    
                    // Get current hash route
                    const hash = window.location.hash;
                    
                    // Get main content area text
                    const main = document.querySelector('main') || document.querySelector('[class*="main"]') || document.body;
                    const allText = main.innerText.substring(0, 3000);
                    
                    // Get all visible buttons/tabs
                    const buttons = Array.from(document.querySelectorAll('button')).map(b => ({
                        text: b.textContent.trim().substring(0, 50),
                        aria: b.getAttribute('aria-label'),
                        disabled: b.disabled
                    })).filter(b => b.text || b.aria).slice(0, 50);
                    
                    // Get all tab/panel elements
                    const tabs = Array.from(document.querySelectorAll('[role="tab"], [data-state]')).map(t => ({
                        text: t.textContent.trim().substring(0, 30),
                        role: t.getAttribute('role'),
                        state: t.getAttribute('data-state')
                    })).slice(0, 30);
                    
                    return JSON.stringify({
                        hash, navItems, 
                        mainText: allText,
                        buttons, tabs,
                        title: document.title
                    });
                })()
            """,
            "returnByValue": True
        })
        val = r.get("result",{}).get("result",{}).get("value","")
        print(val)
    
    elif cmd == "nav":
        # Navigate to a specific page
        target = sys.argv[2] if len(sys.argv)>2 else "market"
        nav_map = {
            "market": "#/market",
            "quote": "#/quote", 
            "volatility": "#/volatility",
            "strategy": "#/strategy",
            "futures": "#/futures",
            "anomaly": "#/anomaly"
        }
        target_hash = nav_map.get(target, f"#/{target}")
        r = send_cmd(ws, "Runtime.evaluate", {
            "expression": f"window.location.hash = '{target_hash}'",
            "returnByValue": True
        })
        print(f"Navigated to {target}: {target_hash}")
        time.sleep(1)
        # Now dump the page content
        r2 = send_cmd(ws, "Runtime.evaluate", {
            "expression": "document.body.innerText.substring(0, 3000)",
            "returnByValue": True
        })
        print(r2.get("result",{}).get("result",{}).get("value",""))
    
    elif cmd == "eval":
        expr = " ".join(sys.argv[2:])
        r = send_cmd(ws, "Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True
        })
        print(json.dumps(r.get("result",{}).get("result",{}), indent=2, ensure_ascii=False))
    
    elif cmd == "snap":
        # Take a screenshot
        r = send_cmd(ws, "Page.captureScreenshot", {"format": "png"})
        import base64
        data = r.get("result",{}).get("data","")
        outfile = sys.argv[2] if len(sys.argv)>2 else "legend_snap.png"
        with open(outfile, "wb") as f:
            f.write(base64.b64decode(data))
        print(f"Screenshot saved: {outfile}")
    
    elif cmd == "list-tables":
        # List all table/grid elements
        r = send_cmd(ws, "Runtime.evaluate", {
            "expression": """
                (() => {
                    const tables = Array.from(document.querySelectorAll('table, [role="grid"], [role="table"], [class*="grid"], [class*="table"]'));
                    return JSON.stringify(tables.map((t,i) => ({
                        idx: i, tag: t.tagName, role: t.getAttribute('role'),
                        className: t.className.substring(0, 80),
                        rows: t.querySelectorAll('tr, [role="row"]').length,
                        text: t.innerText.substring(0, 200)
                    })));
                })()
            """,
            "returnByValue": True
        })
        print(r.get("result",{}).get("result",{}).get("value",""))
    
    elif cmd == "watchlist":
        # Get the watchlist / self-selected items
        r = send_cmd(ws, "Runtime.evaluate", {
            "expression": """
                (() => {
                    // Look for the market page content with text5 pattern
                    const allText = document.body.innerText;
                    // Get all items in the monitoring panel
                    const items = Array.from(document.querySelectorAll('[class*="item"], [class*="row"], [class*="card"]'));
                    const texts = items.map(el => el.innerText.trim().substring(0, 100)).filter(t => t.length > 5);
                    return JSON.stringify({
                        count: texts.length,
                        items: texts.slice(0, 30)
                    });
                })()
            """,
            "returnByValue": True
        })
        print(r.get("result",{}).get("result",{}).get("value",""))
    
    ws.close()

if __name__ == "__main__":
    main()
