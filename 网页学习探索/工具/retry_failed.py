# -*- coding: utf-8 -*-
"""retry_failed.py -- 用 scrapling StealthyFetcher 重试失败的国内链接。"""
import json, os, re, time, sys
from urllib.parse import urlparse
from html.parser import HTMLParser

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LINKS = os.path.join(BASE, "03_qhqqbk/数据/qhqqbk_links.json")
RESULTS = os.path.join(BASE, "03_qhqqbk/数据/fetch_results.jsonl")
ARCHIVE = os.path.join(BASE, "03_qhqqbk/HTML归档")

# 海外域名（永不做）
OVERSEAS = {
    'www.bloomberg.com','www.reuters.com','www.bls.gov','www.bea.gov',
    'www.federalreserve.gov','www.cftc.gov','publicreporting.cftc.gov',
    'www.ecb.europa.eu','www.eia.gov','www.usda.gov','apps.fas.usda.gov',
    'data.nass.usda.gov','www.opec.org','publications.opec.org','www.iea.org',
    'rigcount.bakerhughes.com','www.weather.gov','www.wpc.ncep.noaa.gov',
    'www.nhc.noaa.gov','charts.ecmwf.int','www.ecmwf.int','wmo.int',
    'droughtmonitor.unl.edu','www.cmegroup.com','www.ice.com','www.lme.com','www.sgx.com',
}

class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0; self.blocks = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip += 1
        if self.skip==0 and tag in ('p','div','li','h1','h2','h3','td','th','section','article'): self.blocks.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style') and self.skip > 0: self.skip -= 1
    def handle_data(self, d):
        if self.skip==0 and d.strip(): self.blocks.append(d)

def clean(html):
    p = _P()
    try: p.feed(html)
    except: pass
    return re.sub(r"\n\s*\n+","\n", re.sub(r"[ \t]+"," ","".join(p.blocks))).strip()

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+','_',(s or 'unnamed')[:40]).strip() or 'unnamed'

def main():
    from scrapling.fetchers import StealthyFetcher
    
    # 读取失败的国内链接
    failed_urls = set()
    for l in open(RESULTS, encoding="utf-8"):
        r = json.loads(l)
        if r.get("status") != 200:
            dom = urlparse(r["url"]).netloc
            if dom not in OVERSEAS:
                failed_urls.add(r["url"])
    
    print(f"待重试国内链接: {len(failed_urls)}")
    
    links = json.load(open(LINKS, encoding="utf-8"))
    to_retry = [l for l in links if l["url"] in failed_urls]
    
    ok = 0
    for i, l in enumerate(to_retry, 1):
        url = l["url"]
        name = l.get("name", "unnamed")
        dom = urlparse(url).netloc.replace(".", "_")
        try:
            r = StealthyFetcher.fetch(url, headless=True, timeout=45000, wait_selector="body", wait_selector_state="attached")
            if r.status != 200 or len(r.body) < 200:
                print(f"  [{i}/{len(to_retry)}] SKIP {r.status} {url[:60]}")
                continue
            text = r.body.decode("utf-8", errors="replace")
            sub = os.path.join(ARCHIVE, dom)
            os.makedirs(sub, exist_ok=True)
            hp = os.path.join(sub, f"{l.get('i',i):03d}_{safe_name(name)}.html")
            tp = os.path.join(sub, f"{l.get('i',i):03d}_{safe_name(name)}.txt")
            with open(hp, "w", encoding="utf-8") as f: f.write(text)
            with open(tp, "w", encoding="utf-8") as f: f.write(f"# {name}\n# URL: {url}\n\n{clean(text)}")
            ok += 1
            print(f"  [{i}/{len(to_retry)}] ✅ {len(r.body)}B {url[:60]}")
        except Exception as e:
            print(f"  [{i}/{len(to_retry)}] ERR {str(e)[:50]} {url[:50]}")
        time.sleep(1)
    
    print(f"\n重试完成: {ok}/{len(to_retry)}")

if __name__ == "__main__":
    main()