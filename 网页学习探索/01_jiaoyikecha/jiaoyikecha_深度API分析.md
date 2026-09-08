# 交易可查 jiaoyikecha.com —— 深度API分析报告

> **测试日期**：2026-09-08 12:37 (CST)
> **测试方式**：HTTP 直连 ajax 接口（Node.js https 模块），无浏览器渲染
> **数据时效**：实测数据均为当日盘中/盘后最新

---

## 一、API会话机制（实测验证）

### 1.1 会话三步流程

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: GET  /www.jiaoyikecha.com        → 200, 2177 字节      │
│  Step 2: POST /ajax/session.php?v=5f6760cc → 200, PHPSESSID     │
│  Step 3: POST /ajax/<端点>.php?v=5f6760cc  → 200, JSON 数据      │
└─────────────────────────────────────────────────────────────────┘
```

**实测数据**：

| 步骤 | 方法 | URL | HTTP状态 | 响应大小 | 说明 |
|------|------|-----|----------|----------|------|
| 1 | GET | `/www.jiaoyikecha.com` | 200 | 2,177 bytes | 首页HTML外壳（SPA，JS渲染） |
| 2 | POST | `/ajax/session.php?v=5f6760cc` | 200 | ~200 bytes | 返回PHPSESSID |
| 3 | POST | `/ajax/<端点>.php?v=5f6760cc` | 200 | 变化 | 带Cookie的匿名数据接口 |

### 1.2 PHPSESSID 格式

- **格式**：32位十六进制字符串
- **正则**：`^[0-9a-f]{32}$`
- **实测样例**：`10533e72acc70a7cbfbc049b99f332a6`（已验证通过）
- **写入方式**：从 session.php 响应的 `cookie.PHPSESSID` 字段提取，写入 Cookie 头后续请求使用

### 1.3 session.php 响应结构

```json
{
  "cookie": {
    "PHPSESSID": "10533e72acc70a7cbfbc049b99f332a6",
    "remember": ""
  },
  "data": [],
  "code": 1,
  "msg": ""
}
```

**注意**：`code=1` 表示会话创建成功（非错误码），与数据端点的 `code=0` 含义不同。

### 1.4 统一请求规范

| 参数 | 值 |
|------|-----|
| HTTP方法 | 统一 `POST` |
| URL版本参数 | `?v=5f6760cc`（静态资源版本号） |
| Content-Type | `application/x-www-form-urlencoded` |
| Cookie | `PHPSESSID=<32位hex>` |
| User-Agent | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36` |

---

## 二、匿名可用端点完整测试结果（全部code=0，实测通过）

> 以下为 **2026-09-08 12:37** 实测结果，全部返回 HTTP 200 + code=0

### 2.1 品种/指数/席位辅助端点

| # | 端点 | 说明 | 数据量 | HTTP | code |
|---|------|------|--------|------|------|
| 1 | `all_varieties.php` | 全部品种 | 89条 | 200 | 0 |
| 2 | `official_indexes.php` | 官方指数 | 12条 | 200 | 0 |
| 3 | `all_brokers.php` | 全部席位 | 208条 | 200 | 0 |
| 4 | `variety_families.php` | 品种族 | 15条 | 200 | 0 |
| 5 | `recent_contracts.php` | 近期合约 | 24条 | 200 | 0 |
| 6 | `all_varieties_db.php` | 基本面库品种 | 40条 | 200 | 0 |
| 7 | `report_brokers.php` | 研报席位 | 27条 | 200 | 0 |
| 8 | `items_by_variety.php` | 品种数据项 | 11条 | 200 | 0 |

### 2.2 核心数据端点

| # | 端点 | 说明 | 数据量 | HTTP | code |
|---|------|------|--------|------|------|
| 9 | `daily_wr.php` | 仓单日报 | 76条 | 200 | 0 |
| 10 | `hg.php` | 支撑压力位 | 76条 | 200 | 0 |
| 11 | `broker_trend.php` | 席位资金动向 | 70条 | 200 | 0 |
| 12 | `longhu_list.php` | 龙虎榜 | 10条 | 200 | 0 |
| 13 | `niuxiong_list.php` | 牛熊榜 | 10条 | 200 | 0 |
| 14 | `broker_calendar.php` | 盈亏日历 | 241条 | 200 | 0 |
| 15 | `net_position_list.php` | 净持仓列表 | 22条 | 200 | 0 |

### 2.3 需参数端点（实测通过）

| # | 端点 | 必需参数 | 说明 | 数据量 | HTTP | code |
|---|------|----------|------|--------|------|------|
| 16 | `variety_position.php` | `variety=螺纹钢` | 品种持仓详情 | object（含buy/ss数组） | 200 | 0 |
| 17 | `contract_dates.php` | `variety=螺纹钢` | 品种日期范围 | object | 200 | 0 |
| 18 | `variety_code.php` | `code=rb2701` | 品种代码解析 | object | 200 | 0 |
| 19 | `broker_positions.php` | `broker=国泰君安` | 席位持仓列表 | object（含positions） | 200 | 0 |
| 20 | `index_money.php` | `variety=螺纹钢` | 指数持仓市值 | object（含dates/values） | 200 | 0 |
| 21 | `items_by_variety.php` | `variety=螺纹钢` | 品种数据项 | 11条 | 200 | 0 |

### 2.4 其他匿名端点

| # | 端点 | 说明 | 数据量 | HTTP | code |
|---|------|------|--------|------|------|
| 22 | `spots.php` | 现货报价树 | 8类（树形） | 200 | 0 |
| 23 | `market_temp.php` | 多空领先概览 | object（整数值） | 200 | 0 |
| 24 | `broker_pie.php` | 席位持仓结构 | object | 200 | 0 |
| 25 | `broker_dates.php` | 席位日期范围 | object | 200 | 0 |
| 26 | `wr_dates.php` | 仓单日期范围 | object | 200 | 0 |
| 27 | `fund_dates.php` | 资金日期范围 | object | 200 | 0 |
| 28 | `fundamental_db.php` | 基本面数据库 | object | 200 | 0 |
| 29 | `unusual_quotes.php` | 异动行情 | 0条（非交易时段） | 200 | 0 |

**匿名端点总计：25个端点全部 code=0 通过，0个错误。**

---

## 三、需登录端点（403）

> 以下端点匿名调用返回 HTTP 200 但 JSON code=403，附带中文提示信息

### 3.1 实测 403 端点

| # | 端点 | 403提示信息 | 对应功能 |
|---|------|------------|----------|
| 1 | `variety_trend.php` | 查看"商品持仓市值"请先登录 | 商品涨跌统计 |
| 2 | `broker_profit_loss.php` | 查看"盈亏商品"请先登录 | 席位盈亏 |
| 3 | `deepview_strategies.php` | 查看"龙虎牛熊分析"请先登录 | 策略分析 |
| 4 | `market_temp_line.php` | 查看"多空领先指标"请先登录 | 多空领先指标（时序） |
| 5 | `spots_list.php` | 查看"现货报价"请先登录 | 现货报价详情 |
| 6 | `fund_compare.php` | 查看"市值对比"请先登录 | 资金对比 |
| 7 | `reports_list.php` | 查看"精选研报"请先登录 | 研报列表 |
| 8 | `index_prices_stat.php` | 查看"指数涨跌统计"请先登录 | 指数涨跌 |
| 9 | `deepview_lhnx.php` | 查看"龙虎牛熊一览"请先登录 | 龙虎牛熊分析 |

### 3.2 403 响应结构

```json
{
  "urlPath": "/deepview/market_temp_line",
  "permissionId": null,
  "msg": "查看\"多空领先指标\"请先登录",
  "code": 403
}
```

### 3.3 其他已知需登录端点（来源学习笔记）

```
variety_structure / variety_profit_loss /
broker_table / broker_variety /
deepview_brokers / prices_map /
qk(乾坤归一) / speculation /
toolbox_foreign / temp_quotes /
arbitrage_fut_spot_structure_all /
arbitrage_warehouse / gdp /
fund_deal_pie / fund_bs_pie / fund_big_chge / fund_all
```

**权限说明**：
- 注册免费账号可解锁部分功能（如基础席位数据详情）
- VIP 充值解锁深度分析、资金全景、研报等高端功能
- `menuPermission.php` 控制前端菜单可见性

---

## 四、数据结构详细分析

### 4.1 all_varieties.php — 全部品种（89条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {"market": "上期所", "name": "螺纹钢", "symbol": "RB"},
    {"market": "上期所", "name": "热卷", "symbol": "HC"},
    {"market": "中金所", "name": "300沪深", "symbol": "IF"},
    {"market": "大商所", "name": "铁矿石", "symbol": "I"},
    {"market": "广期所", "name": "碳酸锂", "symbol": "LC"},
    {"market": "郑商所", "name": "纯碱", "symbol": "SA"}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `market` | string | 交易所名称（上期所/中金所/大商所/广期所/郑商所） |
| `name` | string | 品种中文名 |
| `symbol` | string | 品种英文代码（大写） |

**交易所分布**：上期所 25个、中金所 8个、大商所 25个、广期所 6个、郑商所 25个

### 4.2 daily_wr.php — 仓单日报（76条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {
      "name": "螺纹钢",
      "wr_unit": 0.1,
      "total_vol": 134546,
      "total_chge": 0,
      "total_vol2": 13454.6,
      "total_chge2": 0,
      "chge_rate": 0
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 品种名称 |
| `wr_unit` | float | 仓单单位（0.1=吨, 1=吨, 4=吨/手, 8=吨/手） |
| `total_vol` | int | 仓单总量（手） |
| `total_chge` | int | 仓单日变化（手） |
| `total_vol2` | float | 仓单总量（换算后） |
| `total_chge2` | float | 仓单日变化（换算后） |
| `chge_rate` | float | 仓单变化率（%） |

**实测样例**：螺纹钢 134,546 手（wr_unit=0.1），热卷 214,485 手，铁矿石 6,250 手

### 4.3 hg.php — 支撑压力位（76条）

```json
{
  "code": 0,
  "msg": "",
  "time": "09/08 12:37",
  "data": [
    {
      "variety": "螺纹钢",
      "code": "rb2701",
      "current_price": 3168,
      "time": "11:30:00",
      "min15": "<span class='win'>偏多</span>，支撑：3158-3164",
      "min3": "<span>VIP用户可查看</span>...",
      "min60": "<span>VIP用户可查看</span>...",
      "last_close": 3153
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `variety` | string | 品种名称 |
| `code` | string | 合约代码（小写） |
| `current_price` | float | 当前价格 |
| `last_close` | float | 昨收价 |
| `time` | string | 数据时间 |
| `min15` | string | **15分钟支撑压力**（HTML格式，匿名可见） |
| `min3` | string | 3分钟支撑压力（VIP专属） |
| `min60` | string | 60分钟支撑压力（VIP专属） |

**min15 字段解析规则**：
- 偏多：`<span class='win'>偏多</span>，支撑：XXXX-XXXX`
- 偏空：`<span class='loss'>偏空</span>，压力：XXXX-XXXX`
- 震荡：`震荡，压力：XXXX-XXXX，支撑：XXXX-XXXX`

**匿名可用信息**：76个品种的 15分钟支撑压力位全部可见；3分钟和60分钟需VIP。

### 4.4 broker_trend.php — 席位资金动向（70条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {
      "name": "国泰君安",
      "grade": "A",
      "money": 1904738480,
      "order_money": 1904738480,
      "variety": "1000中证"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 期货公司名称 |
| `grade` | string | 席位评级（A/B/C） |
| `money` | float | 资金变动额（元，正=流入，负=流出） |
| `order_money` | float | 委托资金变动额 |
| `variety` | string | 关联品种 |

**实测数据摘要**：国泰君安（A级）最大流入 19.05亿元（1000中证），最大流出 16.67亿元

### 4.5 longhu_list.php — 龙虎榜（10条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {"name": "沪金", "code": "au2612", "longhu": 82.81466271334432},
    {"name": "沪金", "code": "au2704", "longhu": 61.391934286204645},
    {"name": "沪锌", "code": "zn2612", "longhu": 34.770337672936556}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 品种名称 |
| `code` | string | 合约代码（小写） |
| `longhu` | float | 龙虎比（多头/空头席位持仓比，>1偏多） |

**实测样例**：沪金 au2612 龙虎比 82.81（极强多头），沪锌 zn2612 龙虎比 34.77

### 4.6 niuxiong_list.php — 牛熊榜（10条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {"name": "沪金", "code": "au2702", "niuxiong": 50},
    {"name": "沪金", "code": "au2612", "niuxiong": 44},
    {"name": "锰硅", "code": "sm2612", "niuxiong": 39}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 品种名称 |
| `code` | string | 合约代码（小写） |
| `niuxiong` | int | 牛熊分（>0偏牛，越高越牛） |

**实测样例**：沪金 au2702 牛熊分 50（最强牛），锰硅 sm2612 牛熊分 39

### 4.7 official_indexes.php — 官方指数（12条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {"id": "index0d5e051e...", "name": "..."}
  ]
}
```

### 4.8 all_brokers.php — 全部席位（208条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {"name": "APF", "grade": "C", "alpha": "A"}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 期货公司简称 |
| `grade` | string | 综合评级（A/B/C） |
| `alpha` | string | 分类标签（A/B/C） |

### 4.9 spots.php — 现货报价树（8类）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    {"label": "能源", "children": [...]},
    {"label": "化工", "children": [...]},
    {"label": "有色", "children": [...]}
  ]
}
```

树形结构，一级为品类（能源/化工/有色等），二级为具体品种现货报价。

### 4.10 variety_position.php — 品种持仓详情（带参）

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "buy": [
      {"broker_id": 47, "broker": "中信期货", "grade": "A", "buy": 182955, "buy_chge": -7593, "net_position": 78135}
    ],
    "ss": [...],
    "total_buy": ...,
    "total_ss": ...
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `buy` | array | 多头席位持仓排名（前20+） |
| `ss` | array | 空头席位持仓排名 |
| `buy[].broker` | string | 席位名称 |
| `buy[].grade` | string | 评级 |
| `buy[].buy` | int | 多头持仓（手） |
| `buy[].buy_chge` | int | 多头持仓变化 |
| `buy[].net_position` | int | 净持仓 |

### 4.11 broker_positions.php — 席位持仓列表（带参）

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "positions": {
      "鸡蛋": [{"code": "jd2706", "buy": 312, "ss": 786, "buy_chge": -2, "ss_chge": 29, "name": "鸡蛋", "family": "农副"}],
      "螺纹钢": [...]
    }
  }
}
```

按品种分组的席位持仓详情，含主力/非主力合约。

### 4.12 broker_calendar.php — 席位盈亏日历（241条）

```json
{
  "code": 0,
  "msg": "",
  "data": [
    ["2025-09-08", 205008120],
    ["2025-09-09", -150000000]
  ]
}
```

二维数组：`[日期, 盈亏额(元)]`，覆盖约一年交易日。

### 4.13 index_money.php — 指数持仓市值（带参）

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "dates": ["2023-09-11", "2023-09-12", ...],
    "values": [...],
    "year_date": "...",
    "year_data": ...,
    "name": "...",
    "stat_..."
  }
}
```

时间序列数据，含历史日期与对应市值。

---

## 五、与量化数据层协同建议

### 5.1 可直接接入 futures_monitor 的数据

| 数据端点 | 量化用途 | 接入优先级 | 更新频率 |
|----------|----------|-----------|----------|
| `all_varieties.php` | 品种主表（89品种映射） | 高 | 日更 |
| `contract_dates.php` | 交易日历校验 | 高 | 日更 |
| `recent_contracts.php` | 主力/近期合约代码 | 高 | 日更 |
| `daily_wr.php` | 仓单日报 → 库存监控 | 高 | 日更 |
| `hg.php` (min15) | 15分钟支撑压力 → 止损止盈 | 高 | 盘中实时 |
| `broker_trend.php` | 席位资金流向 → 跟踪主力 | 高 | 日更 |
| `longhu_list.php` | 龙虎榜 → 异动信号 | 中 | 日更 |
| `niuxiong_list.php` | 牛熊榜 → 趋势判断 | 中 | 日更 |
| `variety_position.php` | 品种持仓明细 → 多空结构 | 中 | 日更 |
| `broker_calendar.php` | 席位盈亏历史 → 回测参考 | 低 | 日更 |
| `net_position_list.php` | 净持仓排名 → 筛选品种 | 中 | 日更 |
| `official_indexes.php` | 官方指数列表 | 低 | 周更 |
| `spots.php` | 现货报价树 → 基差计算 | 中 | 日更 |
| `items_by_variety.php` | 基本面数据项 | 低 | 周更 |

### 5.2 数据落库建议

```
futures_monitor 数据层扩展：

1. 品种维度表（all_varieties）→ 所有表的外键
2. 仓单日报表（daily_wr）→ 按 date+variety 落库，用于库存趋势分析
3. 支撑压力表（hg_min15）→ 按 date+code 落库，用于日内交易参考
4. 席位资金表（broker_trend）→ 按 date+broker+variety 落库
5. 龙虎牛熊表（longhu+niuxiong）→ 按 date+code 落库
6. 品种持仓明细表（variety_position）→ 按 date+variety 落库
```

### 5.3 关键指标计算公式

```
龙虎比 = longhu_list.longhu（>1多头占优，<1空头占优）
牛熊分 = niuxiong_list.niuxiong（>0偏牛，<0偏空）
资金流向 = broker_trend.money（正=流入，负=流出，单位：元）
仓单变化率 = daily_wr.chge_rate（%）
支撑位 = hg.min15 解析：<span>偏多</span>，支撑：XXXX-XXXX
压力位 = hg.min15 解析：<span>偏空</span>，压力：XXXX-XXXX
```

---

## 六、scrapling工程复用

> 以下工程模式来源于量化项目第94轮对标成果，可直接复用于 jiaoyikecha 采集

### 6.1 A4 会话+Cookie持久化

```python
# 核心流程：GET首页 → POST session.php → Cookie写入后续请求
import requests

def create_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...',
        'Accept': '*/*',
    })
    # Step 1: GET homepage
    s.get('https://www.jiaoyikecha.com/www.jiaoyikecha.com', timeout=15)
    # Step 2: POST session.php
    r = s.post('https://www.jiaoyikecha.com/ajax/session.php?v=5f6760cc', timeout=15)
    # PHPSESSID 自动写入 cookies
    return s
```

**复用要点**：
- Cookie 自动管理（requests.Session 处理 Set-Cookie）
- session.php 返回 `cookie.PHPSESSID` 字段，需手动写入（如使用 curl/httpx）
- 会话有效期：实测至少30分钟无需刷新

### 6.2 A5 请求级限流退避

```python
# 实测安全间隔：0.8~1.2秒/请求
# 25个匿名端点 × 1秒 = 25秒完成全量采集
import time, random

def rate_limited_request(session, url, data=None, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(0.8 + random.uniform(0, 0.4))
            r = session.post(url, data=data, timeout=15)
            return r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                raise
```

**实测限流参数**：
- 0.8秒间隔：安全，无429
- 0.5秒间隔：偶发连接重置
- 建议生产环境：1.0~1.5秒/请求

### 6.3 A1 解析健康探针

```python
def check_health(response_json, endpoint):
    """验证响应结构是否符合预期"""
    if response_json.get('code') != 0:
        raise ValueError(f'{endpoint}: code={response_json.get("code")}, msg={response_json.get("msg")}')
    data = response_json.get('data')
    if data is None:
        raise ValueError(f'{endpoint}: data字段缺失')
    if isinstance(data, list) and len(data) == 0:
        print(f'WARNING: {endpoint}: data为空数组')
    return True
```

### 6.4 B1 浏览器级请求头

```python
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}
```

**实测验证**：标准浏览器 User-Agent 即可，无需 TLS 指纹伪装；如被风控可升级为 scrapling StealthyFetcher。

---

## 七、完整端点清单（32个实测）

### 匿名可用（25个）

| 端点 | 参数 | 数据量 | 说明 |
|------|------|--------|------|
| `all_varieties.php` | 无 | 89 | 全部品种 |
| `daily_wr.php` | 无 | 76 | 仓单日报 |
| `hg.php` | 无 | 76 | 支撑压力位 |
| `broker_trend.php` | 无 | 70 | 席位资金动向 |
| `longhu_list.php` | 无 | 10 | 龙虎榜 |
| `niuxiong_list.php` | 无 | 10 | 牛熊榜 |
| `official_indexes.php` | 无 | 12 | 官方指数 |
| `all_brokers.php` | 无 | 208 | 全部席位 |
| `spots.php` | 无 | 8类 | 现货报价树 |
| `all_varieties_db.php` | 无 | 40 | 基本面品种 |
| `variety_families.php` | 无 | 15 | 品种族 |
| `recent_contracts.php` | 无 | 24 | 近期合约 |
| `market_temp.php` | 无 | int | 多空领先概览 |
| `broker_calendar.php` | 无 | 241 | 盈亏日历 |
| `net_position_list.php` | 无 | 22 | 净持仓列表 |
| `report_brokers.php` | 无 | 27 | 研报席位 |
| `fundamental_db.php` | 无 | obj | 基本面数据库 |
| `unusual_quotes.php` | 无 | 0 | 异动行情 |
| `variety_position.php` | variety= | obj | 品种持仓详情 |
| `contract_dates.php` | variety= | obj | 日期范围 |
| `variety_code.php` | code= | obj | 品种代码 |
| `broker_positions.php` | broker= | obj | 席位持仓 |
| `index_money.php` | variety= | obj | 指数持仓市值 |
| `broker_pie.php` | 无 | obj | 席位持仓结构 |
| `items_by_variety.php` | variety= | 11 | 品种数据项 |

### 需登录（403，7个实测 + 已知约20个）

| 端点 | 403提示 |
|------|---------|
| `variety_trend.php` | 商品持仓市值 |
| `broker_profit_loss.php` | 盈亏商品 |
| `deepview_strategies.php` | 龙虎牛熊分析 |
| `market_temp_line.php` | 多空领先指标 |
| `spots_list.php` | 现货报价 |
| `fund_compare.php` | 市值对比 |
| `reports_list.php` | 精选研报 |
| `index_prices_stat.php` | 指数涨跌统计 |
| `deepview_lhnx.php` | 龙虎牛熊一览 |

---

## 八、采集工程总结

| 维度 | 结果 |
|------|------|
| 匿名可用端点 | 25个（全部 code=0） |
| 需登录端点 | ~27个（code=403） |
| 总品种覆盖 | 89个（5大交易所） |
| 席位覆盖 | 208个 |
| 会话机制 | 3步流程，PHPSESSID 32位hex |
| 限速建议 | 1.0~1.5秒/请求 |
| 采集耗时 | 全量25端点约30秒 |
| 数据格式 | JSON，统一 code/msg/data 结构 |
| 前端技术 | LayUI Admin SPA，hash路由 |
| 静态资源 | static.jiaoyikecha.com/dist/ |
