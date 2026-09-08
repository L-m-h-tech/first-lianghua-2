# -*- coding: utf-8 -*-
"""fetch_qhqqbk_links.py -- 批量抓取 qhqqbk 目录中的全部链接（含所有子链接），归档 HTML 与文本。

- 输入: 03_qhqqbk/数据/qhqqbk_links.json
- 输出: 03_qhqqbk/HTML归档/<域名>/<序号>_<名称>.html / .txt  +  03_qhqqbk/数据/fetch_results.jsonl
- 礼貌限速: 每请求间隔 0.6~1.2s 随机；超时 25s；重试 1 次
- 对标量化项目 http_client A5 退避：遇 429/503 退避 3s 后跳过
"""
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LINKS = os.path.join(ROOT, "03_qhqqbk", "数据", "qhqqbk_links.json")
ARCHIVE = os.path.join(ROOT, "03_qhqqbk", "HTML归档")
RESULT = os.path.join(ROOT, "03_qhqqbk", "数据", "fetch_results.jsonl")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDR = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

_SKIP_TAGS = {"script", "style", "noscript", "template", "iframe", "svg", "head", "title"}
_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
               "table", "thead", "tbody", "tfoot", "tr", "section", "article", "ul", "ol", "blockquote"}


def clean_text(html):
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
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", "".join(p.blocks))).strip()


def safe_name(s, maxlen=40):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s or "unnamed").strip()
    return s[:maxlen] or "unnamed"


def main():
    links = json.load(open(LINKS, encoding="utf-8"))
    print(f"total links: {len(links)}")
    os.makedirs(ARCHIVE, exist_ok=True)
    sess = requests.Session()
    sess.headers.update(HDR)
    results = open(RESULT, "a", encoding="utf-8")
    done = ok = fail = 0
    for i, item in enumerate(links, 1):
        url = item["url"]
        host = urlparse(url).netloc.replace(".", "_")
        name = safe_name(item["name"])
        rec = {
            "i": i, "name": item["name"], "url": url, "category": item.get("category"),
            "kind": item.get("kind"), "ts": datetime.now().strftime("%Y%m%d_%H%M%S"),
        }
        try:
            r = sess.get(url, timeout=25)
            status = r.status_code
            if status in (429, 503):
                time.sleep(3)
        except requests.exceptions.SSLError as e:
            rec["status"] = "ssl_err"; rec["note"] = str(e)[:120]
            results.write(json.dumps(rec, ensure_ascii=False) + "\n"); results.flush()
            fail += 1; time.sleep(random.uniform(0.4, 0.8)); continue
        except Exception as e:
            rec["status"] = "err"; rec["note"] = str(e)[:120]
            results.write(json.dumps(rec, ensure_ascii=False) + "\n"); results.flush()
            fail += 1; time.sleep(random.uniform(0.4, 0.8)); continue

        if status != 200:
            rec["status"] = status
            results.write(json.dumps(rec, ensure_ascii=False) + "\n"); results.flush()
            fail += 1; time.sleep(random.uniform(0.4, 0.8)); continue

        # 尝试按 meta 或头解析编码
        enc = r.encoding or "utf-8"
        m = re.search(rb'charset=["\']?([\w-]+)', r.content[:2048])
        if m:
            enc = m.group(1).decode("ascii", "replace")
        try:
            text = r.content.decode(enc, errors="replace")
        except (LookupError, Exception):
            text = r.content.decode("utf-8", errors="replace")

        sub = os.path.join(ARCHIVE, host)
        os.makedirs(sub, exist_ok=True)
        hp = os.path.join(sub, f"{i:03d}_{name}.html")
        tp = os.path.join(sub, f"{i:03d}_{name}.txt")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(text)
        clean = clean_text(text)
        with open(tp, "w", encoding="utf-8") as f:
            f.write(f"# {item['name']}\n# URL: {url}\n# fetched: {rec['ts']}\n\n{clean}")
        rec["status"] = 200; rec["bytes"] = len(r.content); rec["text_chars"] = len(clean)
        rec["html_file"] = os.path.relpath(hp, ROOT)
        results.write(json.dumps(rec, ensure_ascii=False) + "\n"); results.flush()
        ok += 1
        done += 1
        print(f"[{i}/{len(links)}] {status} {len(r.content):>7}B {url[:80]}", flush=True)
        time.sleep(random.uniform(0.6, 1.2))
    results.close()
    print(f"DONE ok={ok} fail={fail}")


if __name__ == "__main__":
    main()