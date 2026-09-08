# -*- coding: utf-8 -*-
"""fetch_page.py -- 抓取网页并归档（对标量化项目从 scrapling 学到的工程增强）。
抓取带浏览器级请求头（B1 stealth headers 子集），响应落 HTML归档/，同时输出
文本化（A3 html_text 思路）与响应头/状态审计日志。零网络失败时打印可读原因。

用法:
  python fetch_page.py <name> <url> [--out-dir DIR]
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS_BROWSER = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}
_SKIP_TAGS = {"script", "style", "noscript", "template", "iframe", "svg", "head", "title"}
_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
               "table", "thead", "tbody", "tfoot", "tr", "section", "article", "ul", "ol", "blockquote"}


def clean_text(html, max_len=None):
    """去 script/style/注释、块级换行、空白折叠（stdlib 版 html_text.clean_text）。"""
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip = 0
            self.blocks = []

        def handle_starttag(self, tag, attrs):
            if tag in _SKIP_TAGS:
                self.skip += 1
            if self.skip == 0 and tag in _BLOCK_TAGS:
                self.blocks.append("\n")

        def handle_endtag(self, tag):
            if tag in _SKIP_TAGS and self.skip > 0:
                self.skip -= 1

        def handle_data(self, data):
            if self.skip == 0 and data.strip():
                self.blocks.append(data)

    p = _P()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    text = re.sub(r"[ \t]+", " ", "".join(p.blocks))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:max_len] if max_len else text


def extract_links(html, base_url):
    """提取页面全部 href -> 绝对 URL 列表（去重保序）。"""
    from urllib.parse import urljoin, urlparse
    links = []
    seen = set()
    for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I):
        raw = m.group(1)
        if raw.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
            continue
        abs_url = urljoin(base_url, raw)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        links.append(abs_url)
    return links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("url")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--cookie-init", default=None,
                    help="若指定，先 GET 该 URL（JS-cookie 反爬初始化，对标 B4）")
    args = ap.parse_args()

    root = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    web_dir = os.path.join(root, args.name, "HTML归档")
    txt_dir = os.path.join(root, args.name, "数据")
    os.makedirs(web_dir, exist_ok=True)
    os.makedirs(txt_dir, exist_ok=True)

    sess = requests.Session()
    sess.headers.update(HEADERS_BROWSER)

    if args.cookie_init:
        try:
            r0 = sess.get(args.cookie_init, timeout=25)
            print(f"[cookie-init] {args.cookie_init} -> {r0.status_code} cookies={list(sess.cookies.keys())}")
        except Exception as e:
            print(f"[cookie-init] FAIL: {e}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        r = sess.get(args.url, timeout=30)
    except Exception as e:
        print(f"FETCH_FAIL {args.url}: {e}", flush=True)
        sys.exit(2)
    html = r.content
    enc = r.encoding or "utf-8"
    try:
        text = html.decode(enc, errors="replace")
    except Exception:
        text = html.decode("utf-8", errors="replace")

    base_name = args.name + "_" + ts
    html_path = os.path.join(web_dir, base_name + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(text)
    clean = clean_text(text)
    txt_path = os.path.join(txt_dir, base_name + "_text.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(clean)
    meta_path = os.path.join(txt_dir, base_name + "_meta.json")
    import json
    links = extract_links(text, args.url)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "url": args.url, "ts": ts, "status": r.status_code,
            "encoding": enc, "final_url": r.url,
            "bytes": len(html), "text_chars": len(clean),
            "headers_ok": dict(r.headers) if r.headers.get("Content-Length") else {},
            "n_links": len(links), "links": links[:200],
            "cookies": {k: v for k, v in sess.cookies.items()},
        }, f, ensure_ascii=False, indent=1)
    print(f"OK {args.name} status={r.status_code} bytes={len(html)} text={len(clean)} links={len(links)}")
    print(f"  html: {html_path}")
    print(f"  text: {txt_path}")


if __name__ == "__main__":
    main()