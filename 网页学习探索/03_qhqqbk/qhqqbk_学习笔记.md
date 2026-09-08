# 期货期权百科 qhqqbk.com —— 深度学习笔记（重点站）

> 学习日期：2026-09-08 · 全站数据已解析 + 219 个链接逐一抓取归档
> 站点性质：**期货/期权资源综合导航站**（"你所需要的期货网站都在这里"）

## 一、站点概览

- **域名**：`https://www.qhqqbk.com/`（标题：期货期权百科 | qhqqbk.com，备案沪ICP备2025154658号-3，投诉邮箱 postmaster@qhjvs.com）
- **技术栈**：纯静态站（HTML + `app-data.js` + `app.js` + `styles.css`，无后端）
- **核心数据**：全部在 `https://www.qhqqbk.com/app-data.js` —— 一个 `window.SITE_CATEGORIES` JSON 数组，包含**全站目录**
- 页面分类：`categoryNav`/`categoryGrid` 由 JS 渲染；带搜索/筛选（`emptyState` 无结果提示）

## 二、全站目录（8 分类 · 64 站点 · 155 子链接 · 219 链接 · 75 唯一域名）

完整树见 `数据/qhqqbk_目录树.md`，JSON 见 `数据/qhqqbk_links.json`。结构速览：

| 分类 | 站点数 | 说明 |
|------|-------|------|
| 🏛️ 交易所官方 | 9 | 中金所/上期所/能源中心/郑商所/大商所/广期所/证监会/中期协（+持仓排名/公告/仓单子链接） |
| 📰 新闻资讯 | 4 | 金十期货/新浪期货/东方财富期货/华尔街见闻 |
| 🌐 海外资讯 | 17 | 彭博/路透/BLS/BEA/美联储/CFTC/ECB/EIA/USDA/OPEC/IEA/贝克休斯/NOAA/ECMWF/WMO/USDM/CME/ICE/LME/SGX |
| 💻 交易软件 | 7 | 文华财经/博易大师/同花顺期货通/易信快期/无限易/交易开拓者/极星 |
| 📈 数据渠道 | 3 | AKShare/Tushare/天勤量化 |
| 🖥️ 期货金融终端 | 3 | Wind/iFinD/上海钢联终端 |
| 🧭 分板块专业机构 | 13 | 上海钢联/兰格/隆众/卓创/涌益/粮油信息/上海有色/长江有色/百川/金联创/生意社/钢之家/openvlab |
| 🏆 期货比赛 | 6 | 实盘大赛/大盘手/夺冠高手/金牛至赢/期航杯(高校)/期货寻星 |

## 三、链接抓取审计（219 链接逐一抓取）

- **成功归档 187/219（85%）**：HTML + 清洗文本按域名存 `HTML归档/<域名>/`（如 `www_czce_com_cn/`）
- 抓取方式两级：
  1. 普通 requests + 浏览器头（对标量化 B1）——成功 169
  2. **scrapling StealthyFetcher 反检测浏览器**（绕过 JS 挑战）——追加成功 18（郑商所 412→200、大商所 412→200、LME、博易大师、涌益等）
- **失败 32 个均为海外站点网络封锁**（非技术可解）：
  - 403（17）：BLS/USDA/OPEC/IEA/CFTC（Akamai 边缘按 IP 封锁，qhqqbk 自身也标注"国内无法直连"）
  - 连接超时（15）：Bloomberg/Reuters/CME（国内网络无法直连）
- 可访问性审计全表：`数据/qhqqbk_审计.md`

## 四、重点站点内容要点（从归档文本提炼）

### 交易所官方（国内 5 所 + 监管）
- **中金所 cffex.com.cn**：`/cn/index.html` 首页；`/cn/ccpm.html` 会员成交持仓排名；`/cn/jysgg.html` 公告
- **上期所 shfe.com.cn**：持仓排名/公告/仓单走 `reports/tradedata/dailyandweeklydata/?query_params=pm|dailystock`
- **能源中心 ine.cn**：同上结构（原油/低硫燃料油/国际铜）
- **郑商所 czce.com.cn**（stealth 已归档）：持仓排名 `/cn/jysj/ccpm/H077003004index_1.htm`、公告 `/cn/gyjys/jysdt/ggytz/H077001003001index_1.htm`、仓单 `/cn/jysj/cdrb/H077003010index_1.htm`
- **大商所 dce.com.cn**（stealth 已归档）：持仓 `/dce/channel/list/176.html`、公告 `244.html`、仓单 `187.html`
- **广期所 gfex.com.cn**：持仓 `/gfex/rcjccpm/hqsj_tjsj.shtml`、公告 `/gfex/tzts/list_yw.shtml`、仓单 `/gfex/cdrb/hqsj_tjsj.shtml`
- **证监会 csrc.gov.cn**、**中期协 cfachina.org**（含期货公司 app 查询、品种手册）

### 数据渠道（与量化直接相关）
- **AKShare**（`akshare.akfamily.xyz`）：开源金融数据接口库，文档含 数据字典/接口检索/量化专题；GitHub `akfamily/akshare`
- **Tushare**（`tushare.pro`）：数据开放社区（量化项目已有 `tushare_client.py` 接入，token 走 .env）
- **天勤量化**（`shinnytech.com/tianqin`）：TqSdk API 文档在 `doc.shinnytech.com/tqsdk/latest/`

### 交易软件/终端
- 文华 WH6（`wh6.wenhua.com.cn`）、博易大师（`boyidashi.com`）、同花顺期货通（`download.10jqka.com.cn`）、快期（`shinnytech.com/products/q73`）、无限易（`infinitrader.quantdo.com.cn`）、交易开拓者（`tbq.tbquant.net`）、极星（`epolestar.esunny.com.cn/download`）、Wind（`wind.com.cn`）、iFinD（`51ifind.com`）、钢联终端（`data.mysteel.com`）

### 分板块产业数据
- 黑色：钢联 `mysteel.com`/兰格 `lgmi.com`/钢之家 `steelhome.com`
- 能化：隆众 `oilchem.net`/卓创 `sci99.com`/百川 `baiinfo.com`/金联创 `315i.com`
- 农业：涌益 `yongyizixun.com`/粮油信息 `chinagrain.cn`
- 有色：上海有色 `smm.cn`/长江有色 `ccmn.cn`
- 现货：生意社 `100ppi.com`（大宗商品涨跌榜/基准价格/报价中心/AI行情分析/定价中心/商品与宏观/产业/期货/证券）
- **openvlab.cn**：期权专业网站（即本学习任务②）

### 期货比赛（含最新赛季信息，2026）
- 第二十届全国期货(期权)实盘大赛 `ds.qhrb.com.cn`（期货日报×证券时报，2026-03-27~09-30）
- 大盘手 `dpswang.com/futures`（2026-06-01~2027-05-31）
- 夺冠高手第九届 `dggaoshou.com`（2025-12-29~2026-10-31）
- 金牛至赢 `ifutures.cs.com.cn`（中证报，2026-05-18~10-31）
- 期航杯高校赛（cfachina 页面，2026-09-07~11-06）
- 期货寻星投顾选拔赛 `touguwang.cn`（2025-11-01~2026-10-31）

### 海外数据（标注访问限制）
- 彭博/路透/CME/ICE/LME/SGX（外盘交易所）、BLS/BEA/美联储/CFTC（美国官方数据）、EIA/USDA/OPEC/IEA（能源农产品）、NOAA/ECMWF/WMO/USDM（天气气候）、贝克休斯钻机数 —— **国内网络多数无法直连**，需代理；其中 **LME 已在 stealth 下成功归档**

## 五、技术结论

1. **qhqqbk 是纯导航站，自身无数据接口**，价值 = **全市场资源地图**（已完整解析 + 归档）
2. 数据获取渠道按类别整理：国内交易所数据→官网直连（郑商所/大商所需 stealth）；行情→新浪/东财/金十；产业数据→钢联/隆众/卓创/生意社；量化数据→AKShare/Tushare/天勤；期权→openvlab；外盘→LME/SGX 可连，彭博/路透/CME 需代理
3. **scrapling StealthyFetcher 在本任务的实战价值**：CZCE/DCE 的 412 JS 挑战、LME 的防护，requests 无法访问而 stealth 全部拿下
4. 站点对抓取友好：静态 JSON 数据结构化程度高，`app-data.js` 直接可解析，无需渲染

## 六、文件索引

- `数据/app-data.js`（原始目录数据）、`数据/qhqqbk_目录树.md`（完整树）、`数据/qhqqbk_links.json`（219 链接 JSON）、`数据/qhqqbk_stats.json`（统计）、`数据/qhqqbk_审计.md`（可访问性审计）
- `HTML归档/<域名>/*.html|.txt`（219 个链接归档，stealth 重试成功的有 `_stealth` 后缀）
- `数据/fetch_results.jsonl`（首抓日志）、`数据/fetch_results_retry.jsonl`（stealth 重试日志）