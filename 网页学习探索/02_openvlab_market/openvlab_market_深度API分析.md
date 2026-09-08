# OpenVLab 市场 openvlab.cn/market —— 深度API分析报告

> 测试日期：2026-09-08 · 所有端点均已实测通过
> 站点性质：**期权波动率专业站**（Next.js React SPA，后端 FastAPI）
> 数据归档：`raw/` 目录含全部响应快照与HTTP头

---

## 一、API架构概述

### 1.1 技术栈

- **前端**：Next.js React SPA（`/_next/static` chunk 按需加载）
- **后端**：FastAPI（pydantic 校验、响应统一 `{code, result, message}` 格式）
- **端口**：标准 HTTPS 443，域名 `www.openvlab.cn`

### 1.2 统一API格式

```
GET https://www.openvlab.cn/api/<endpoint>
```

响应结构：
```json
{
  "code": 0,
  "result": { ... },
  "message": "ok"
}
```

- `code=0` 表示成功，非零为错误
- `message` 始终为 `"ok"`（成功时）
- `result` 类型因端点而异：数组 / 对象 / 嵌套对象

### 1.3 与桌面端 Legend 的关系

桌面端 **OpenVLab Legend**（Electron 客户端）的**行情界面数据全部来自这些匿名 REST API**。桌面端另有一个 cfwtd 网关（`127.0.0.1` 动态端口 WebSocket，"一行一个 JSON"），但该网关仅用于 **SimNow 模拟交易链路**，不涉及行情数据传输。

---

## 二、元数据端点（全部实测通过）

### 2.1 /api/exchange-info —— 交易所列表

**请求**：`GET /api/exchange-info`

**响应**：8个交易所

| 编号 | exchange | exchange_name | 说明 |
|------|----------|---------------|------|
| 1 | CFFEX | 中金所 | 中国金融期货交易所 |
| 2 | SHSE | 上交所 | 上海证券交易所 |
| 3 | SZSE | 深交所 | 深圳证券交易所 |
| 4 | SHFE | 上期所 | 上海期货交易所 |
| 5 | DCE | 大商所 | 大连商品交易所 |
| 6 | CZCE | 郑商所 | 郑州商品交易所 |
| 7 | INE | 能源中心 | 上海国际能源交易中心 |
| 8 | GFEX | 广期所 | 广州期货交易所 |

### 2.2 /api/sector-info —— 板块列表

**请求**：`GET /api/sector-info`

**响应**：6个板块

| 编号 | sector | sector_alias | 覆盖品种举例 |
|------|--------|--------------|-------------|
| 1 | EQ | 股指 | IO/IO/HO/MO + ETF期权 |
| 2 | MT | 金属 | AU/AG/CU/AL/ZN/NI/SN/PB/BC/AO/AD/PT/PD |
| 3 | EN | 能化 | EG/TA/MA/PP/L/V/RU/BU/FU/SC/BR/PG 等 |
| 4 | AG | 农副 | C/CS/SR/CF/AP/JD/CJ/PK/LH |
| 5 | OS | 油脂 | P/OI/RM/A/B/Y/M |
| 6 | BK | 黑色 | I/J/JM/RB/SM/SF/SI/PS/LC/LG |

### 2.3 /api/product-exps?add_overseas=true —— 品种+到期月

**请求**：`GET /api/product-exps?add_overseas=true`

**响应**：83个品种（含ETF期权与海外品种），每个品种含完整的到期月列表

**返回字段**：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| sector | string | 板块代码 | `"EN"` |
| sector_alias | string | 板块中文名 | `"能化"` |
| gui_order | float | 界面排序权重 | `7.0` |
| product | string | 期权品种代码（含`_O`后缀） | `"EG_O"` |
| product_und | string | 标的品种代码 | `"EG"` |
| product_alias | string | 品种中文名 | `"乙二醇"` |
| symbol | string | 期权合约前缀 | `"OPT_DCE_EG"` |
| symbol_und | string | 标的合约前缀 | `"FUT_DCE_EG"` |
| has_night_trading | int | 是否有夜盘（1=有） | `1` |
| is_overseas | string | 是否海外品种（`"0"`=国内） | `"0"` |
| exchange | string | 交易所 | `"DCE"` |
| exps | array | 到期月列表 | 见下 |
| front_exp | string | 近月合约到期月 | `"202610"` |
| precision_und | int | 标的价格小数位 | `0` |
| precision | int | 期权价格小数位 | `1` |
| minMove_und | float | 标的最小变动 | `1.0` |
| minMove | float | 期权最小变动 | `0.5` |

**到期月（exps）结构**：
```json
{
  "exp": 202610,           // 到期月（YYYYMM格式）
  "expDate": "20260916",   // 最后交易日
  "limit_up": 6149.0,      // 涨停价
  "limit_down": 5453.0     // 跌停价
}
```

**83品种分布统计**：
- 股指板块（EQ）：16个（含IO/HO/MO + 上证50ETF/300ETF/500ETF/创业板ETF/科创50ETF等 + 港股HHI/HSI/HSTECH）
- 金属板块（MT）：15个（含AU/AG/CU/AL/ZN/NI/SN/PB/BC/AO/AD/PT/PD + 美黄金GC/美铜HG/美银SIL）
- 能化板块（EN）：25个（含EG/TA/MA/PP/L/V/RU/BU/FU/SC/BR/PG/BZ/EB/PF/SH/SA/FG/PR/PX/NR/SP/OP/PL/PR + 美原油CL）
- 农副板块（AG）：9个（C/CS/SR/CF/AP/JD/CJ/PK/LH）
- 油脂板块（OS）：7个（P/OI/RM/A/B/Y/M）
- 黑色板块（BK）：11个（I/J/JM/RB/SM/SF/SI/PS/LC/LG）

### 2.4 /api/auth/user —— 登录态

**请求**：`GET /api/auth/user`

**响应**：
```json
{"code": 0, "result": {"authenticated": false, "user": null}, "message": "ok"}
```

匿名状态下 `authenticated=false`，可正常调用所有公开端点。

---

## 三、核心行情端点（装置 openvlab_collector 已接入）

### 3.1 /api/ctamap-all?add_overseas=true —— 全品种期权波动率地图

**请求**：`GET /api/ctamap-all?add_overseas=true`

**响应**：83条记录，约38KB，每条记录对应一个品种的近月期权波动率摘要

**完整字段说明**：

| 字段 | 类型 | 说明 | 实测示例（EG） |
|------|------|------|---------------|
| sector | string | 板块代码 | `"EN"` |
| sector_alias | string | 板块中文名 | `"能化"` |
| product | string | 期权品种代码 | `"EG_O"` |
| product_alias | string | 品种中文名 | `"乙二醇"` |
| prodUnd | string | 标的代码 | `"EG"` |
| is_overseas | string | 是否海外 | `"0"` |
| exchange | string | 交易所 | `"DCE"` |
| has_night_trading | string | 是否夜盘 | `"1"` |
| exp | string | 近月到期月 | `"202610"` |
| expiry_date | string | 到期日 | `"2026-09-16"` |
| last_time | string | 最后更新时间 | `"2026-09-08 11:30:00"` |
| price | string | 标的最新价 | `"5808.0"` |
| rv22 | string | 22日历史波动率 | `"46.16"` |
| atmv_current | string | 当前ATM隐含波动率 | `"46.81"` |
| atmv_percentile | string | ATM隐波百分位（0-100） | `"88.02"` |
| atmv_1dchg | string | ATM隐波日变化 | `"-5.12"` |
| carry | string | 波动率溢价（隐波-实波） | `"0.65"` |
| skew_current | string | 当前偏度 | `"0.53"` |
| skew_percentile | string | 偏度百分位 | `"48.95"` |
| skew_1dchg | string | 偏度日变化 | `"-0.09"` |
| ctn | string | Contango因子 | `"0.0061"` |
| frontfwd_mom | string | 近远月动量 | `"-0.0863"` |
| valphaT | string | Alpha值 | `"-0.324"` |

**实测数据快照（2026-09-08午盘，部分品种）**：

| 品种 | 中文名 | 标的价格 | ATM隐波 | 隐波百分位 | 22日实波 | 溢价 | 偏度 |
|------|--------|---------|---------|-----------|---------|------|------|
| EG_O | 乙二醇 | 5808.0 | 46.81 | 88.02 | 46.16 | 0.65 | 0.53 |
| V_O | PVC | 4954.0 | 28.11 | 87.60 | 30.00 | -1.89 | 0.20 |
| CF_O | 郑棉 | 16615.0 | 14.19 | 67.36 | 8.57 | 5.62 | 1.77 |
| AU_O | 沪金 | 959.34 | 24.85 | 59.50 | 23.95 | 0.90 | 1.90 |
| CU_O | 沪铜 | 110690.0 | 17.10 | 39.67 | 11.57 | 5.53 | 1.96 |
| AG_O | 沪银 | 16313.0 | 42.81 | 29.88 | 41.67 | 1.14 | 2.14 |
| SC_O | 原油 | 703.2 | 46.07 | 51.24 | 53.00 | -6.93 | 1.43 |
| BU_O | 沥青 | 5139.0 | 38.95 | 87.82 | 26.70 | 12.25 | -0.87 |
| JM_O | 焦煤 | 1629.5 | 45.25 | 69.68 | 37.72 | 7.53 | -2.03 |
| NR_O | 20号胶 | 16575.0 | 31.32 | 95.74 | 16.80 | 14.52 | 2.33 |
| RU_O | 橡胶 | 19605.0 | 24.27 | 97.52 | 13.71 | 10.56 | 1.68 |
| 50ETF | 上证50ETF | 3.025 | 13.67 | 18.60 | 11.12 | 2.55 | -0.05 |
| 300ETF | 沪深300ETF | 4.643 | 16.31 | 42.98 | 13.96 | 2.35 | -0.77 |

### 3.2 /api/dto/{code} —— 单标的行情详情

**请求**：`GET /api/dto/EG`（code 为标的代码，如 EG/RB/AU/510050 等）

**响应**：约94KB，含标的合约链全部行情数据

**顶层结构**：
```json
{
  "code": 0,
  "result": {
    "headline": null,          // 财报事件标题（股票用）
    "isDelayed": false,        // 是否延迟数据
    "requiresAgreement": false,// 是否需要协议
    "events": {                // 财务事件
      "earnings": [],
      "dividends": [],
      "splits": []
    },
    "context": {               // 核心数据
      "r": { ... },            // 利率曲线
      "i": {                   // 合约链
        "s": [ ... ],          // 交易时段配置
        "i": [ ... ]           // 各合约行情数组
      }
    }
  }
}
```

**合约链字段（context.i.i 数组元素）**：

| 字段 | 说明 | 示例 |
|------|------|------|
| s | 合约代码 | `"EG2610"` |
| n | 合约中文名 | `"乙二醇2610"` |
| l | 最新价 | `5808.0` |
| p | 结算/昨收 | `5773.0` |
| b | 买一价 | `5808.0` |
| a | 卖一价 | `5811.0` |
| v | 成交量 | `1492203` |
| o | 持仓量 | `365725` |
| ua | 更新时间(UTC) | `"2026-09-08T11:30:00Z"` |
| cc | cc代码 | `"eg2610"` |
| x | 乘数 | `10.0` |
| pf.decimals | 小数位 | `0` |
| pf.increment | 最小变动 | `1.0` |

**利率曲线（context.r）**：
```json
{
  "1d": 0.01586,    // 隔夜利率
  "7d": 0.01786,    // 7日利率
  "14d": 0.02078,
  "30d": 0.02398,
  "91d": 0.0245,
  "183d": 0.02498,
  "274d": 0.02515,
  "365d": 0.02532
}
```

### 3.3 /api/volatility-surface/{code} —— 期权波动率曲面

**请求**：`GET /api/volatility-surface/EG`

**响应**：约28KB，按到期月分组的完整期权曲面数据

**顶层结构**：key 为到期月（如 `202610`/`202611`/`202612`/`202701`）

**到期月内字段（以 202610 为例）**：

| 字段 | 说明 | 示例 |
|------|------|------|
| product | 品种代码 | `"EG_O"` |
| exp | 到期月 | `"202610"` |
| expiry_date | 到期日 | `"20260916"` |
| days_to_expiry | 剩余天数 | `8` |
| forward_td | 当日远期价格 | `5812.07` |
| forward_yd | 昨日远期价格 | `5771.53` |
| atmvol_tday | 当日ATM隐波 | `46.8278` |
| atmvol_yday | 昨日ATM隐波 | `51.9255` |
| atmv_current | 当前ATM隐波（from ctamap） | `46.81` |
| maturity_tday | 当日到期时间(年) | `0.0247063` |
| maturity_yday | 昨日到期时间(年) | `0.02781` |
| prior_date | 前一交易日 | `"2026-09-07"` |
| last_time | 最后更新 | `"2026-09-08 11:29:37"` |
| is_ready_fit | 是否可拟合（1.0=是） | `"1.0"` |
| move_up | 标的上涨时隐波变化 | `0.0591` |
| move_dn | 标的下跌时隐波变化 | `-0.0591` |
| rho_tday | 当日rho | `0.58` |
| rho_yday | 昨日rho | `0.62` |
| valphaT | Alpha值 | `-0.311043` |
| display_strike | 显示行权价范围 | `"[5100.0, 6400.0]"` |
| trading_strike | 有成交的行权价范围 | `"[5300.0, 6300.0]"` |

**关键数组字段**：

| 字段 | 说明 | 格式 |
|------|------|------|
| mktvol_tday_call_bid | 看涨买入隐波 | `[[行权价, 隐波/空], ...]` |
| mktvol_tday_call_ask | 看涨卖出隐波 | 同上 |
| mktvol_tday_put_bid | 看跌买入隐波 | 同上 |
| mktvol_tday_put_ask | 看跌卖出隐波 | 同上 |
| theovol_tday | 当日理论隐波 | `[[行权价, 隐波], ...]` |
| theovol_yday | 昨日理论隐波 | 同上 |
| delta_tday_call | 看涨delta | `[[行权价, delta], ...]` |
| delta_tday_put | 看跌delta | 同上 |
| pdf_list | 隐波率分布 | `[[价格, 概率], ...]` |
| strike_oid_c | 看涨持仓量变化 | `{"行权价": 变化量}` |
| strike_oid_p | 看跌持仓量变化 | 同上 |
| strike_poi_c | 看涨持仓量 | 同上 |
| strike_poi_p | 看跌持仓量 | 同上 |
| sum_oi_call | 看涨总持仓 | `114239` |
| sum_oi_put | 看跌总持仓 | `269662` |
| sum_poi_call | 看涨持仓变化 | `105126` |
| sum_poi_put | 看跌持仓变化 | `265490` |

**EG品种实测曲面结构**：

| 到期月 | 天数 | ATM隐波 | 远期价 | 看涨持仓 | 看跌持仓 |
|--------|------|---------|--------|---------|---------|
| 202610 | 8天 | 46.83 | 5812.07 | 114,239 | 269,662 |
| 202611 | 45天 | 41.39 | 5423.65 | 13,203 | 24,728 |
| 202612 | 71天 | 39.15 | 5182.53 | 254 | 79 |
| 202701 | 106天 | 30.76 | 4929.55 | 297 | 336 |

**曲面特征观察**：
- 近月（202610）隐波最高（46.83），远月递减至30.76，呈现明显的**期限结构backwardation**
- 近月行权价范围 5100-6400，远月扩展至 3700-5600
- 看跌持仓远大于看涨持仓（269k vs 114k），put/call ratio > 2

---

## 四、受限端点

| 端点 | 方法 | 限制说明 |
|------|------|---------|
| `/api/volatility-surface-yday` | GET | 需登录态（匿名 404） |
| `/api/watchlist/*` | GET | 需登录态（自选功能） |
| `/api/price-volatility-series` | POST | 需登录/付费条件满足才返回数据 |
| `/api/influencer` | GET | 部分数据需登录 |
| `/api/legend` | GET | 客户端信息，部分受限 |

**price-volatility-series 请求格式**：
```json
POST /api/price-volatility-series
Body: {"codes": "EG"}   // 注意：codes 为字符串，非数组
```
实测匿名返回 `{"code": 0, "result": [], "message": "ok"}`（result 为空数组）。

---

## 五、社区/其他端点

市场页同源的辅助端点（均已实测）：

| 端点 | 说明 | 状态 |
|------|------|------|
| `/api/community/live-streams/today?limit=100` | 今日直播流 | 正常 |
| `/api/partners/profiles?userIds=...` | 合作伙伴资料 | 正常 |
| `/api/influencer` | 达人信息 | 正常 |
| `/api/legend` | 客户端版本信息 | 正常 |
| `/api/monitoring` | 埋点上报（POST） | 500 为正常行为 |

---

## 六、与桌面端 Legend 的对应关系

### 6.1 数据来源映射

| Legend 功能 | 数据来源 | 对应API |
|------------|---------|---------|
| 行情界面（品种列表） | 匿名REST | `/api/ctamap-all` |
| 行情详情（标的合约） | 匿名REST | `/api/dto/{code}` |
| 波动率曲面（2D/3D） | 匿名REST | `/api/volatility-surface/{code}` |
| SimNow模拟交易 | WebSocket | cfwtd 网关（`127.0.0.1` 动态端口） |

### 6.2 关键结论

- **行情数据完全不依赖 cfwtd 网关**，全部来自 `www.openvlab.cn/api/*` 匿名端点
- cfwtd 网关仅用于 SimNow 登录/下单/持仓等交易操作
- 免费/Pro 划分：仅夜盘/外盘、3D曲面、持仓排名完整期限图表为 Pro；2D曲面/策略优选/异动榜/日历免费
- 桌面端 `instrument-cache/*.json` 含91期货+91期权合约元数据

---

## 七、数据采集结论

### 7.1 核心价值

1. **openvlab 是免费权威的期权波动率数据源**：ctamap-all 一站 83 品种 ATM 隐波/百分位/偏度/溢价，surface 提供按月完整曲面（与新浪期权链互补，且覆盖 ETF 期权）
2. 三端点全匿名、全实测 code=0，`add_overseas=true` 增加海外品种（83 vs 76 无外盘）
3. 数据流架构：
   - `ctamap-all` → **全市场隐波扫描**（找隐波异动/溢价机会）
   - `dto/{code}` → **标的价格与事件**（合约链行情）
   - `volatility-surface/{code}` → **任意品种分月曲面** → 驱动量化侧 `iv_surface`/`option_chain` 与装置 dashboard 三级下钻

### 7.2 采集建议

1. **请求头**：建议携带浏览器 UA + Referer（`https://www.openvlab.cn/market`），避免被限流
2. **采集频率**：ctamap-all 建议每30秒轮询（交易时段）；surface 建议每5分钟
3. **限流风险**：本机多次连续探测均 200，限流风险较低
4. **异常处理**：`code != 0` 时记录日志，等待重试

### 7.3 跨源冲突检测

装置侧已落地 openvlab 价格与 legend/ths 同品种比对，偏差 >1% 时触发告警。

---

## 八、scrapling 工程模式复用

从量化项目第94轮对标成果中复用的工程模式：

1. **统一请求封装**：所有 openvlab 请求复用同一 session/UA/超时配置
2. **响应校验**：统一检查 `code == 0`，异常时降级到上次缓存
3. **增量更新**：ctamap-all 按 `last_time` 字段判断是否需要更新
4. **曲面解析**：volatility-surface 响应按到期月自动分组，无需额外解析
5. **合约链映射**：dto 响应中 `context.i.i` 数组自动映射为标准合约链格式
6. **错误重试**：网络异常自动重试3次，指数退避

---

## 附录A：文件归档清单

```
raw/
├── body_exchange_info.json      # 交易所列表响应
├── body_sector_info.json        # 板块列表响应
├── body_product_exps.json       # 品种+到期月响应（83条）
├── body_user.json               # 登录态响应
├── body_ctamap.json             # 全品种波动率地图（无外盘）
├── body_ctamap_overseas.json    # 全品种波动率地图（含外盘）
├── body_dto_AU.json             # 沪金标的行情
├── body_dto_EG.json             # 乙二醇标的行情
├── body_dto_RB.json             # 螺纹钢标的行情
├── body_vol_AU.json             # 沪金波动率曲面
├── body_vol_EG.json             # 乙二醇波动率曲面
├── body_vol_RB.json             # 螺纹钢波动率曲面
├── hdr_*.txt                    # 各端点HTTP响应头
├── h_*.headers.txt              # 各端点完整HTTP头
└── js_bundles.txt               # 前端JS bundle路径
```

---

## 附录B：完整端点清单

| # | 方法 | 端点 | 需登录 | 说明 |
|---|------|------|--------|------|
| 1 | GET | `/api/exchange-info` | 否 | 交易所列表 |
| 2 | GET | `/api/sector-info` | 否 | 板块列表 |
| 3 | GET | `/api/product-exps?add_overseas=true` | 否 | 品种+到期月 |
| 4 | GET | `/api/auth/user` | 否 | 登录态 |
| 5 | GET | `/api/ctamap-all?add_overseas=true` | 否 | 全品种波动率地图 |
| 6 | GET | `/api/dto/{code}` | 否 | 单标的行情 |
| 7 | GET | `/api/volatility-surface/{code}` | 否 | 期权曲面 |
| 8 | POST | `/api/price-volatility-series` | 是 | 价格-波动率时序 |
| 9 | GET | `/api/volatility-surface-yday` | 是 | 昨日曲面 |
| 10 | GET | `/api/watchlist/*` | 是 | 自选列表 |
| 11 | GET | `/api/community/live-streams/today` | 否 | 今日直播流 |
| 12 | GET | `/api/partners/profiles` | 否 | 合作伙伴资料 |
| 13 | GET | `/api/influencer` | 部分 | 达人信息 |
| 14 | GET | `/api/legend` | 否 | 客户端版本 |
| 15 | POST | `/api/monitoring` | 否 | 埋点上报 |
