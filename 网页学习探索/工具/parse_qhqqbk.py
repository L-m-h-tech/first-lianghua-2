# -*- coding: utf-8 -*-
"""parse_qhqqbk.py -- 解析 qhqqbk.com 的 app-data.js 目录数据，生成完整树形笔记与全链接清单。

输出（均在 03_qhqqbk/ 下）：
  - 数据/qhqqbk_目录树.md         人类可读完整目录树（分类→站点→子链接+标签）
  - 数据/qhqqbk_links.json        全部链接（去重），含 名称/url/描述/父分类/是否子链接
  - 数据/qhqqbk_stats.json        统计（分类数/站点数/链接数/唯一域名数）
"""
import json
import os
import re
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "03_qhqqbk", "数据")


def parse_app_data(path):
    raw = open(path, encoding="utf-8").read()
    # 去掉前缀 window.SITE_CATEGORIES = 与结尾分号
    m = re.search(r"window\.\w+\s*=\s*(\[.*\])\s*;?\s*$", raw, re.S)
    if not m:
        m = re.search(r"=\s*(\[.*)", raw, re.S)
    return json.loads(m.group(1))


def walk(categories):
    """yield (层级, 名称, url, 描述, tags, 是否子链接)。"""
    for cat in categories:
        yield (1, "分类", cat.get("title"), None, cat.get("description"), None, False)
        for site in cat.get("sites", []):
            yield (2, "站点", site.get("name"), site.get("url"), site.get("description"), None, False)
            for ch in site.get("children", []):
                yield (3, "子链", ch.get("name"), ch.get("url"), ch.get("description"), ch.get("tags"), True)


def main():
    src = os.path.join(DATA, "app-data.js")
    cats = parse_app_data(src)

    lines = ["# qhqqbk.com 期货期权百科 —— 完整目录树", ""]
    stats = {"categories": 0, "sites": 0, "links": 0, "children": 0, "domains": set()}
    all_links = []

    for cat in cats:
        stats["categories"] += 1
        lines.append(f"## {cat.get('icon','')} {cat['title']}")
        lines.append("")
        if cat.get("description"):
            lines.append(f"> {cat['description']}")
            lines.append("")
        for site in cat.get("sites", []):
            stats["sites"] += 1
            stats["links"] += 1
            dom = urlparse(site["url"]).netloc
            if dom:
                stats["domains"].add(dom)
            all_links.append({
                "kind": "site", "name": site.get("name"), "url": site.get("url"),
                "description": site.get("description"), "category": cat["title"],
                "tags": None,
            })
            lines.append(f"### 🔗 {site['name']}")
            lines.append(f"- 链接: <{site['url']}>")
            if site.get("description"):
                lines.append(f"- 说明: {site['description']}")
            children = site.get("children", [])
            if children:
                lines.append(f"- 子链接（{len(children)} 个）:")
                for ch in children:
                    stats["children"] += 1
                    stats["links"] += 1
                    cdom = urlparse(ch["url"]).netloc
                    if cdom:
                        stats["domains"].add(cdom)
                    all_links.append({
                        "kind": "child", "name": ch.get("name"), "url": ch.get("url"),
                        "description": ch.get("description"), "category": cat["title"],
                        "tags": ch.get("tags"), "parent": site["name"],
                    })
                    tags = " ".join(f"`{t}`" for t in (ch.get("tags") or []))
                    lines.append(f"    - {ch['name']} — <{ch['url']}> {('('+tags+')') if tags else ''}"
                                 f"{(' — '+ch['description']) if ch.get('description') else ''}")
            lines.append("")
        lines.append("")

    # 写目录树
    tree_path = os.path.join(DATA, "qhqqbk_目录树.md")
    with open(tree_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 写全链接 JSON
    links_path = os.path.join(DATA, "qhqqbk_links.json")
    with open(links_path, "w", encoding="utf-8") as f:
        json.dump(all_links, f, ensure_ascii=False, indent=1)

    # 统计
    domains = sorted(stats["domains"])
    stats["domains"] = domains
    stats["unique_domains"] = len(domains)
    with open(os.path.join(DATA, "qhqqbk_stats.json"), "w", encoding="utf-8") as f:
        json.dump({k: (v if not isinstance(v, set) else sorted(v)) for k, v in stats.items()},
                  f, ensure_ascii=False, indent=1)

    print(f"categories={stats['categories']} sites={stats['sites']} children={stats['children']} "
          f"total_links={stats['links']} unique_domains={stats['unique_domains']}")
    print("tree:", tree_path)


if __name__ == "__main__":
    main()