# -*- coding: utf-8 -*-
"""fetch_qhqqbk_retry.py -- 对初次抓取失败的 qhqqbk 链接用 scrapling StealthyFetcher（反检测浏览器）重试。
输出到 03_qhqqbk/HTML归档/<域名>/ 追加到 fetch_results_retry.jsonl。
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LINKS = os.path.join(ROOT, "03_qhqqbk", "数据", "qhqqbk_links.json")
RESULTS = os.path.join(ROOT, "03_qhqqbk", "数据", "fetch_results.jsonl")
ARCHIVE = os.path.join(ROOT, "03_qhqqbk", "HTML归档")
OUT = os.path.join(ROOT, "03_qhqqbk", "数据", "fetch_results_retry.jsonl")


def clean_text(html):
    from html.parser import HTMLParser

    _SKIP = {"script", "style", "noscript", "template", "iframe", "svg", "head", "title"}
    _BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
              "table", "thead", "tbody", "tfoot", "tr", "section", "article", "ul", "ol", "blockquote"}

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip = 0
            self.blocks = []

        def handle_starttag(self, tag, attrs):
            if tag in _SKIP:
                self.skip += 1
            if self.skip == 0 and tag in _BLOCK:
                self.blocks.append("\n")

        def handle_endtag(self, tag):
            if tag in _SKIP and self.skip > 0:
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
    from scrapling.fetchers import StealthyFetcher
    links = json.load(open(LINKS, encoding="utf-8"))
    failed = {}
    for line in open(RESULTS, encoding="utf-8"):
        r = json.loads(line)
        if r.get("status") != 200:
            failed[r["url"]] = r
    print(f"retry candidates: {len(failed)}")

    out = open(OUT, "a", encoding="utf-8")
    ok = fail = 0
    for i, (url, old) in enumerate(failed.items(), 1):
        rec = {"i": old.get("i"), "name": old.get("name"), "url": url,
               "category": old.get("category"), "kind": old.get("kind"),
               "first_status": old.get("status"), "ts": datetime.now().strftime("%Y%m%d_%H%M%S")}
        try:
            r = StealthyFetcher.fetch(url, headless=True, timeout=45000,
                                      wait_selector="body", wait_selector_state="attached")
            status = r.status
            body = r.body
        except Exception as e:
            rec["status"] = "stealth_err"; rec["note"] = str(e)[:100]
            out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
            fail += 1
            print(f"[{i}/{len(failed)}] ERR {url[:70]}", flush=True)
            continue

        if status != 200 or len(body) < 500:
            rec["status"] = status; rec["note"] = f"len={len(body)}"
            out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
            fail += 1
            print(f"[{i}/{len(failed)}] {status} len={len(body)} {url[:70]}", flush=True)
            continue

        host = urlparse(url).netloc.replace(".", "_")
        text = body.decode("utf-8", errors="replace")
        sub = os.path.join(ARCHIVE, host)
        os.makedirs(sub, exist_ok=True)
        hp = os.path.join(sub, f"{rec['i']:03d}_{safe_name(rec['name'])}_stealth.html")
        tp = os.path.join(sub, f"{rec['i']:03d}_{safe_name(rec['name'])}_stealth.txt")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(text)
        clean = clean_text(text)
        with open(tp, "w", encoding="utf-8") as f:
            f.write(f"# {rec['name']}\n# URL: {url}\n# fetched(stealth): {rec['ts']}\n\n{clean}")
        rec["status"] = 200; rec["bytes"] = len(body); rec["text_chars"] = len(clean)
        rec["html_file"] = os.path.relpath(hp, ROOT)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        ok += 1
        print(f"[{i}/{len(failed)}] OK {status} {len(body)}B {url[:70]}", flush=True)
        time.sleep(1.0)
    out.close()
    print(f"DONE stealth ok={ok} fail={fail}")


if __name__ == "__main__":
    main()