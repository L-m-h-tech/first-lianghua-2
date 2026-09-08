# 网页学习探索 —— 学习索引

> 本文件夹是 2026-09-08 会话中针对三个期货/期权相关网站的**深度学习成果库**。
> 目标：熟练掌握三个网站的使用与数据获取，为「界面操作收集装置」与「量化」项目的数据层提供支撑。
> 学习全程数据（HTML归档/API探测/截图/笔记）全部存放于此。

## 三个网站

| # | 网站 | 类型 | 学习笔记 | 状态 |
|---|------|------|----------|------|
| 1 | [交易可查 jiaoyikecha.com](https://www.jiaoyikecha.com/www.jiaoyikecha.com) | 期货持仓/席位/基本面数据分析站（LayUI SPA） | [01_jiaoyikecha/jiaoyikecha_学习笔记.md](01_jiaoyikecha/jiaoyikecha_学习笔记.md) | ✅ 已完成（API 地图 + 匿名接口验证） |
| 2 | [OpenVLab 市场 openvlab.cn/market](https://www.openvlab.cn/market) | 期权波动率专业站（Next.js） | [02_openvlab_market/openvlab_market_学习笔记.md](02_openvlab_market/openvlab_market_学习笔记.md) | ✅ 已完成（REST API 全端点验证） |
| 3 | [期货期权百科 qhqqbk.com](https://www.qhqqbk.com/) | 期货资源综合导航站（静态站） | [03_qhqqbk/qhqqbk_学习笔记.md](03_qhqqbk/qhqqbk_学习笔记.md) | ✅ 已完成（目录树全解析 + 219 链接逐一抓取） |

## 目录结构

```
网页学习探索/
  README.md                    本索引
  01_jiaoyikecha/              交易可查
    jiaoyikecha_学习笔记.md     完整笔记（功能地图 + API 端点 + 会话流程）
    HTML归档/                  首页/渲染页 HTML
    数据/                      menu.json / api_probe.json / 网络捕获 / 路由截图
  02_openvlab_market/          OpenVLab 市场
    openvlab_market_学习笔记.md  完整笔记（页面结构 + REST API 全端点）
    HTML归档/                  渲染页 HTML
    数据/                      网络捕获 / API 快照
  03_qhqqbk/                   期货期权百科（重点）
    qhqqbk_学习笔记.md          完整笔记（8 分类 64 站点 219 链接 + 可访问性审计）
    HTML归档/<域名>/            219 个链接的 HTML+文本归档（含 stealth 重试）
    数据/                      目录树 / 链接清单 / 抓取结果 / stats
  04_调研资料/                  jiaoyikecha 混淆 JS 存档等
  05_截图归档/                  各站界面截图
  工具/                        venv + 全部学习脚本（fetch/capture/probe/parse）
```

## 技术要点（从量化项目 scrapling 对标学习沿用）

学习过程复用了量化项目第94轮对标 GitHub scrapling 项目的工程增强（详见
`量化\futures_monitor\CHANGELOG.md` / `html_text.py` / `http_client.py`）：

- **B1 浏览器级请求头**：完整 Accept/Accept-Language/Sec-Fetch-* 头降低限流与拦截概率
- **A4 每源会话 + cookie 持久化**：jiaoyikecha 必须先 `POST /ajax/session.php` 拿 PHPSESSID 才能调数据接口
- **A5 请求级限流退避**：429/503 → 指数退避，礼貌限速 0.6~1.2s/请求
- **A1 解析健康探针 / A3 统一文本表格提取**：归档时统一 clean_text（去 script/style、块级换行）
- **scrapling 本体（pip 安装，venv 内）**：`StealthyFetcher`（undetected 浏览器）绕过 CZCE/DCE 等 412 JS 挑战；`DynamicFetcher`（playwright）渲染 LayUI/Next.js SPA

## 与量化/装置项目的数据层协同

- **openvlab**：`ctamap-all`（83 品种波动率地图）、`dto/{code}`（标的数据）、`volatility-surface/{code}`（按月曲面）为装置/量化提供**匿名可用**的权威期权数据源（装置已有 `openvlab_collector.py` 接入）。
- **jiaoyikecha**：`variety_position.php` / `broker_positions.php` / `daily_wr.php` / `hg.php` 等约 30 个**匿名可调**端点可提供：席位持仓、龙虎牛熊、仓单日报、支撑压力位等数据——可作为量化侧新数据源候选。
- **qhqqbk**：纯导航站，价值在于**全市场资源地图**（交易所/海外数据源/交易软件/数据渠道/比赛），已按域名归档便于检索。

## 使用方式

```bash
# 用系统 Python 跑分析脚本（requests/lxml 已有）
D:\Python\python.exe 工具/parse_qhqqbk.py

# 用 venv 跑渲染/反爬（playwright/scrapling 已装）
工具/venv/Scripts/python.exe 工具/capture_net.py <name> <url>
工具/venv/Scripts/python.exe 工具/capture_routes.py 01_jiaoyikecha <base> route1 route2 ...
```
