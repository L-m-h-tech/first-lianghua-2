# OpenVLab 市场 openvlab.cn/market —— 深度学习笔记

> 学习日期：2026-09-08 · 数据归档于 `HTML归档/` 与 `数据/`
> 站点性质：**期权波动率专业站**（Next.js React SPA，后端 FastAPI）

## 一、网站概览

- **域名**：`https://www.openvlab.cn/market`（市场页）；另有 `api.openvlab.cn`（需软件内 token 的 MCP 服务器，匿名不可用）
- **技术栈**：前端 Next.js（`/_next/static` chunk），后端 FastAPI（`/api/*`，pydantic 校验、响应统一 `{code, result, message}`）
- 与桌面端 **OpenVLab Legend**（Electron 客户端，`E:\OpendVlab Legend\openvlab-legend`）同源：桌面端界面行情即来自这些**匿名 REST API**
- 已登录状态：`/api/auth/user` 返回 `{authenticated:false, user:null}`（匿名可调）

## 二、市场页结构（实测渲染）

**顶部导航**：市场 / 行情 / 波动率 / 期货 / 异动 / 策略 / 交易 / 排行 / 线下课（与 Legend 桌面端 6 导航同体系扩展版）

**市场页区块**：
1. **筛选栏**：板块 / 交易所 / 自选 tabs；仅夜盘、外盘开关；板块：股指/金属/能化/农副/油脂/黑色
2. **隐波最大↑/↓ 榜**（各 5）：名称 / 涨幅% / 隐波变化 / 分时预览（例：尿素+0.17% IV+2.76；硅铁-4.48% IV-13.65）
3. **波动率溢价 最高/最低 榜**（各 5）：名称 / 隐波 / 实波 / 溢价（例：沥青 42.21/26.70/+15.51；丙烯 26.62/34.16/-7.54）
4. **全品种表**（"选择品种"）：名称 / 最新价 / 标的涨幅% / 剩余时间 / 平值隐波 / 隐波变化 / 隐波涨速 / 实波 / 溢价 / 偏度 / 隐波百分位 / 偏度百分位 / 走势预览 —— **83 个品种全在此表**
5. 底部推广：OpenVlab Legend 模拟交易终端下载

## 三、REST API 端点（匿名可用，全部实测）

统一：`GET https://www.openvlab.cn/api/<ep>`，响应 `{"code":0,"result":...}`（`message:"ok"`）

### 元数据
| 端点 | 说明 | 实测 |
|------|------|------|
| `GET /api/exchange-info` | 交易所列表 | CFFEX中金所/SHSE上交所/SZSE深交所/DCE大商所/SHFE上期所/INE能源中心/GFEX广期所/CZCE郑商所 |
| `GET /api/sector-info` | 板块列表 | EQ股指/MT金属/EN能化/AG农副/OI油脂/BK黑色（+别名） |
| `GET /api/product-exps?add_overseas=true` | 品种+到期月 | 83 条（含 ETF 期权与海外品种） |
| `GET /api/auth/user` | 登录态 | `{authenticated:false,user:null}` |

### 核心行情（重点，装置 openvlab_collector 已接入）
| 端点 | 说明 | 实测 |
|------|------|------|
| `GET /api/ctamap-all?add_overseas=true` | **全品种期权波动率地图** | 83 品种，38KB。字段：`sector/sector_alias/product(EG_O)/product_alias(乙二醇)/prodUnd(EG)/is_overseas/exchange/has_night_trading/exp(202610)/rv22(46.16)/expiry_date/last_time/ctn(-0.0057)/price(5740.0)/frontfwd_mom(0.3669)/atmv_current(46.19)/atmv_percentile(88.02)/atmv_1dchg(-5.36)/carry/skew_current/skew_percentile/skew_1dchg/...` |
| `GET /api/dto/{code}` | 单标的行情 | 94KB。`{headline, isDelayed, requiresAgreement, events, context}`；code 支持 `EG`(品种) / `510050`(ETF) 等 |
| `GET /api/volatility-surface/{code}` | 按月期权曲面 | 28KB。key=到期月(`202610/202611/202612/202701`)；内含 mktvol/atmv/forward/delta/希腊字母/持仓变化/PDF 分布 |
| `POST /api/price-volatility-series` | 价格-波动率时序 | 请求体 `{codes:"..."}`（字符串，pydantic 校验）。实测 `{codes:"EG"}` 返回 200 result=[]（需登录/付费条件满足才出数据） |
| `GET /api/volatility-surface-yday` | 昨日曲面 | 需登录态（匿名 404，沿用桌面端认知） |
| `GET /api/watchlist/*` | 自选 | 需登录态 |

### 社区/其他（市场页同源）
`GET /api/community/live-streams/today?limit=100`（今日直播流）、`GET /api/partners/profiles?userIds=...`（合作伙伴资料）、`GET /api/influencer`、`GET /api/legend`（客户端信息）、`GET /api/monitoring`（埋点，POST 500 正常）、`POST /monitoring`（POST 500 属正常埋点失败）。

## 四、与桌面端 Legend 的对应关系（沿用自量化上下文摘要）

- 桌面端 cfwtd 网关（`127.0.0.1` 动态端口 WebSocket，"一行一个 JSON"）仅用于 **SimNow 登录/交易链路**；**行情数据实际全部来自上面这些匿名 REST API**
- 桌面端 `instrument-cache/*.json`：91 期货 + 91 期权合约元数据；`product_param.json` 白名单；`config_simnow.ini`（SimNow broker 9999）
- 免费/Pro 划分：仅夜盘/外盘、3D 曲面、持仓排名完整期限图表为 Pro；2D 曲面/策略优选/异动榜/日历免费
- 跨源冲突检测已在装置侧落地：openvlab 价格与 legend/ths 同品种比对 >1% 告警

## 五、可采集结论

1. **openvlab 是免费权威的期权波动率数据源**：ctamap-all 一站 83 品种 ATM 隐波/百分位/偏度/溢价，surface 提供按月完整曲面（与新浪期权链互补，且覆盖 ETF 期权）
2. 三端点全匿名、全实测 code=0，`add_overseas=true` 增加海外品种（83 vs 76 无外盘）
3. 数据流：ctamap-all 可做**全市场隐波扫描**（找隐波异动/溢价机会）；dto 提供标的价格与事件；volatility-surface 提供任意品种分月曲面 → 可驱动量化侧 iv_surface/option_chain 与装置 dashboard 三级下钻
4. `POST /api/price-volatility-series` 的 codes 为字符串（非数组），满足登录/付费条件后返回 `[{prices:[["时间",价],...], vol:...}]` 结构（从市场页抓包确认）
5. 限流风险低（本机多次连续探测均 200）；建议仍带浏览器 UA + Referer

## 六、页面截图与归档

- 渲染页 HTML：`HTML归档/02_openvlab_market_rendered.html`（255KB 完整 DOM）
- 渲染文本：`数据/market_rendered_text.txt`
- 网络捕获：`数据/02_openvlab_market_network.json`（21 个 xhr/fetch）
- API 快照：`数据/openvlab_api_快照.json`（ctamap/dto_EG/surface_EG/sector/exchange/product_exps 全量）