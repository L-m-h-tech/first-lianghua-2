# 交易可查 jiaoyikecha.com —— 深度学习笔记

> 学习日期：2026-09-08 · 数据全部归档于 `HTML归档/` 与 `数据/`
> 站点性质：**期货持仓/席位/基本面数据分析站**（LayUI Admin SPA，PHP 后端）

## 一、网站概览

- **域名**：`https://www.jiaoyikecha.com/www.jiaoyikecha.com`（首页即该 URL，另有 `jiaoyikecha.com`）
- **关键词**：Deepview / 持仓成本 / 建仓过程 / 乾坤归一 / 支撑压力 / 基差分析 / 现货报价 / 套利分析 / 仓单查询 / 龙虎比 / 牛熊线
- **技术栈**：前端 LayUI Admin（`layui.use('index')` 模块化 SPA，hash 路由 `#/路由`），静态资源在 `static.jiaoyikecha.com`，后端 PHP（`ajax/*.php` 为主要 JSON 接口，`api/v2/*` 为新一代接口）
- **原始 HTML 只有 2.3KB 外壳**（`<div id="LAY_app">` 由 JS 渲染），**必须浏览器渲染或直连 ajax 接口**取数
- 备案号：粤ICP备2023067465号；统计：百度统计 + 站长统计(CNZZ)

## 二、功能地图（/ajax/menu.php 返回的完整菜单）

```
个人中心: 我的主页
VIP服务
指数:    指数详情 / 指数涨跌统计 / 指数持仓市值 / 指数资金动向 / 指数持仓结构 / 指数盈亏详情 / 多指数分析
商品:    持仓详情 / 商品涨跌统计 / 净持仓数据 / 商品持仓市值 / 持仓结构 / 盈亏席位
席位:    持仓列表 / 盈亏日历 / 大资金动向 / 持仓结构 / 盈亏商品 / 建仓过程 / 席位对对碰 / 席位大全
实时深度分析(Deepview): 多空领先指标 / 日内推土机 / 支撑压力位 / 乾坤归一 / 商品投机度 /
                        热度图 / 相关性分析 / 盘后外盘涨跌 / 龙虎牛熊一览 / 龙虎牛熊分析 / 席位四象图
基本面: 数据库(新) / 现货报价
        期现分析: 基差一览 / 基差分析 / 期限一览 / 期限结构 / 库存数据 / 利润数据
        套利分析: 跨期价差 / 自由价差 / 自由价比 / 多腿组合
        仓单分析: 仓单日报 / 仓单查询 / 虚实盘比
        模型分析: 库存基差利润模型
        季节分析: 现货季节图 / 期货季节图
        各地区经济数据
AI研报资讯: AI研报(新) / 精选研报
资金:    市值对比 / 成交额分布 / 净持仓分布 / 机构动向 / 持仓全景图
其他:    下载APP / 帮助视频 / 期货开户 / 关于我们
```

## 三、关键访问流程（重点！）

```text
1. GET  https://www.jiaoyikecha.com/www.jiaoyikecha.com        ← 拿到页面(外壳)
2. POST https://www.jiaoyikecha.com/ajax/session.php?v=5f6760cc  ← 响应 JSON 里有 {cookie:{PHPSESSID:...}}
   把 PHPSESSID 写入 cookie（domain=www.jiaoyikecha.com, path=/）
3. POST https://www.jiaoyikecha.com/ajax/<端点>.php?v=5f6760cc   ← 带 PHPSESSID 即可匿名调用数据接口
```

- 接口统一 `POST`，数据参数用表单（`Content-Type: application/x-www-form-urlencoded`），URL 带 `?v=5f6760cc`（静态资源版本号）
- 大部分数据接口**匿名可用**（code=0）；部分功能（深度分析/资金/研报等）需登录，未登录返回 `code=403` + "请先登录" / "请先充值"
- 典型参数（以螺纹钢为例）：`variety=螺纹钢&code=rb2701&date=2026-09-07`
- 幂等辅助接口：`all_varieties.php`（89品种）、`official_indexes.php`（12指数）、`all_brokers.php`（208席位）、`variety_families.php`（15族）、`contract_dates.php` / `broker_dates.php` / `fund_dates.php` / `wr_dates.php`（各模块日期范围）、`variety_code.php` / `recent_contracts.php`（主连与近期合约）

## 四、匿名可用数据端点（实测 code=0，30+ 个）

| 端点 | 说明 | 返回结构样例 |
|------|------|-------------|
| `variety_position.php` | 品种持仓详情 | `{buy:[{broker_id,broker,grade,buy,buy_chge,net_position}], ss, total_buy,...}`（20+席位） |
| `variety_code.php` | 品种代码解析 | `{variety:"螺纹钢", code:""}` |
| `variety_contracts.php` | 品种合约列表 | `{main_contracts, basis}` |
| `variety_families.php` | 品种族（15） | `["黑色","煤炭","软商品","农副","轻工","化工","油脂油料","有色","贵金属","原油",...]` |
| `all_varieties.php` | 全部品种（89） | `[{market:"上期所", name:"螺纹钢", symbol:"RB"}]` |
| `official_indexes.php` | 官方指数（12） | `[{id:"index0d5e051e...", name,...}]` |
| `index_money.php` | 指数持仓市值 | `{dates, values, year_date, year_data, name, stat_...}` |
| `indexes_trend.php` | 指数资金动向 | 812 条 `[{broker,grade,variety,money(持仓市值),...}]` |
| `indexes_profit_loss.php` | 指数盈亏详情 | `{indexes, value, trans_date, name}` |
| `broker_positions.php` | 席位持仓列表 | `{positions:{品种:[{code,buy,ss,buy_chge,ss_chge,name,family}...]}, date, broker}` |
| `broker_dates.php` | 席位日期范围 | `{last_date:"2026-09-07", first_date:"2023-09-07"}` |
| `broker_trend.php` | 席位大资金动向 | 70 条 `[{name:"国泰君安", grade:"A", money:1904738480,...}]` |
| `broker_pie.php` | 席位持仓结构 | `{legends, date, datas1, datas2}` |
| `broker_calendar.php` | 席位盈亏日历 | 242 条 `[["2025-09-08",205008120],...]`（日期,盈亏额） |
| `all_brokers.php` | 全部席位（208） | `[{name:"APF", grade:"C", alpha:"A"}]` |
| `net_position_list.php` | 净持仓列表 | `[{broker:"上海中期", net_position:600, ...}]` |
| `recent_contracts.php` | 近期合约与持仓市值 | `[{code:"rb2701", value:1121773572828}]` |
| `contract_dates.php` | 品种日期范围 | `{last_date, first_date}` |
| `longhu_list.php` | 龙虎榜（10） | `[{name:"沪金", code:"au2612", longhu:82.8,...}]` |
| `niuxiong_list.php` | 牛熊榜（10） | `[{name:"沪金", code:"au2702", niuxiong:50}]` |
| `hg.php` | 支撑压力位（77） | `[{variety:"20号胶", code:"nr2611", current_price,...}]` |
| `market_temp.php` | 多空领先（首页概览） | `int`（指数值） |
| `unusual_quotes.php` | 异动行情 | `[{...}]` |
| `fundamental_db.php` | 基本面数据库 | `{dates, data, year_date, year_data, stat_data,...}` |
| `fundamental_db_info.php` | 基本面数据（毛利等） | `[{variety:"螺纹钢", name:"华北高炉毛利", val:-103.72, data_date:"2026-09-03", chge:-47.61}]` |
| `all_varieties_db.php` | 基本面库品种（40） | `[{name, symbol, market}]` |
| `items_by_variety.php` | 品种数据项 | `["重点企业粗钢日均产量",...]`（11+ 项） |
| `spots.php` | 现货报价树 | `[{label:"能源", children:[...]}]` |
| `daily_wr.php` | 仓单日报（76） | `[{name:"螺纹钢", wr_unit:0.1, total_vol:134546,...}]` |
| `wr_dates.php` | 仓单日期范围 | `{last_date, first_date}` |
| `fund_dates.php` | 资金日期范围 | `{last_date, first_date}` |
| `report_brokers.php` | 研报席位（27） | `[{label:"一德期货", value:1, children:[...]}]` |
| `deepview_lhnx.php`(页面内) | 龙虎牛熊一览 | 数组：`[牛熊分,日变,市值,code,名称,龙虎比,日变,族]` |
| `space/arbitrage_basis_all.php` | 基差一览 | `[]`（当前空） |

## 五、需登录/VIP 的端点（匿名返回 403）

```
variety_trend / variety_structure / variety_profit_loss / index_prices_stat /
broker_profit_loss / broker_table / broker_variety / deepview_lhnx / deepview_strategies /
deepview_brokers / prices_map / qk(乾坤归一) / speculation / toolbox_foreign /
market_temp_line(多空领先指标) / temp_quotes / spots_list / arbitrage_fut_spot_structure_all /
arbitrage_warehouse / gdp / fund_compare / fund_deal_pie / fund_bs_pie / fund_big_chge /
fund_all / reports_list
```
> 403 响应形如 `{"urlPath":"/deepview/market_temp_line","permissionId":null,"msg":"查看"多空领先指标"请先登录","code":403}`。
> 其中部分端点其实是页面内"未登录时隐藏"：直接调 ajax 需要登录态；注册/登录后（免费账号）部分解锁，VIP 充值解锁更多。

## 六、页面路由与静态资源

- hash 路由：`https://www.jiaoyikecha.com/www.jiaoyikecha.com#/variety/position` 等（跳转均以菜单 `jump` 为准）
- 静态资源：`https://static.jiaoyikecha.com/dist/`（views/*.html 视图模板 + 混淆 JS），版本参数 `?v=5f6760cc`
- 首页加载的视图模板：`layout.html / user/home.html / template/guangao.html / template/user_home_top.html / template/fundamental_db_new.html / template/recommend_reports.html / template/market_temp.html`
- 首页 XHR 序列（实测）：session → menu → notice(公告) → guangao(广告) → menuPermission → da(仪表盘) → marquee(跑马灯) → search → user_home_top → fundamental_db_new(基本面数据库) → recommend_reports(推荐研报) → home_flow → market_temp(多空领先) → home_money_flow(资金流)
- 新一代 API：`POST /api/v2/aireport / aireportHot / aireportByName`（AI 研报，返回分页结构 `{code,message,data,page,trackId,timestamp}`；匿名可返回 200 但 code=502 需登录/参数）

## 七、可直接应用于采集的结论

1. **jiaoyikecha 是免费权威的"席位持仓/龙虎牛熊/仓单/基本面"数据源**，匿名可用约 30 个端点，比逐页 OCR 高效得多
2. 获取方式：requests 会话三步流程（首页→session.php→带参 POST），无需渲染；如被风控可用 scrapling StealthyFetcher
3. 数据质量：全为交易所官方数据（龙虎榜/仓单日报/持仓排名口径），`grade`（评级 A/B/C）与 `alpha`（分类）字段可直接用
4. 与量化联动候选：`all_varieties.php`(品种表) `contract_dates.php`(交易日历校验) `daily_wr.php`(仓单) `hg.php`(支撑压力) `broker_trend.php`(资金动向) 均可落库
5. 限制：指数/资金/深度分析类需登录；免费与 VIP 权限等级明显（`menuPermission.php` 控制）

## 八、常见问题速查

- **"参数错误或数据不存在"（code=1）**：多半是品种名/合约代码/date 格式不匹配，先用 `all_varieties.php` / `recent_contracts.php` / `contract_dates.php` 拿合法值
- **403 请先登录**：该模块需登录或 VIP，换匿名可用端点
- **页面空白**：SPA 未渲染，直接用 ajax 接口
- **curl 直接调数据接口 403 但浏览器内正常**：缺 PHPSESSID，先走 session.php 流程