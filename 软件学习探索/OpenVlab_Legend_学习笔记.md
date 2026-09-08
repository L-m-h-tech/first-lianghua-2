# OpenVlab Legend 软件学习笔记

> 学习日期：2026-09-06（深夜实测）｜ 目的：认识本软件 + 学会使用（配合同花顺期货通做界面数据采集）
> 方法：活动窗口 + UIA 无障碍树 + CDP(9225) DOM 检查 + 安装目录/运行时文件勘察 + 联网调研

---

## 1. 基本信息

| 项 | 值 |
|---|---|
| 软件名 | OpenVlab Legend（桌面客户端），品牌 OpenVlab |
| 定位 | 专业期权研究与波动率分析平台（官网自述），面向期货/期权/证券的桌面终端 |
| 安装位置 | `E:\OpendVlab Legend\openvlab-legend` |
| 主程序 | `openvlab-legend.exe`（Electron v0.0.82，当前线上最新 0.0.98） |
| 官网 | https://www.openvlab.cn （下载 https://www.openvlab.cn/legend ；教学中心 https://www.openvlab.cn/teaching ） |
| 用户数据 | `C:\Users\Lenovo\AppData\Roaming\openvlab-legend` |
| 进程 | openvlab-legend.exe → 渲染后多进程；本地 CTP 网关 cfwtd.exe（随登录拉起） |
| 账号 | SimNow 模拟（当前已登录，动态权益约 200 万）；预留实盘 CTP |
| 协议 | 界面 = Electron 渲染 React+Tailwind；行情数据 = openvlab.cn REST API + 本地 cfwtd WebSocket |

## 2. 界面结构（逐模块实测记录）

### 2.1 整体布局
```
┌──────────────────────────────────────────────────────────────┐
│ header: [交易台logo] [工作区tab: 模拟账号 ×][+新建] [缩小][放大][关闭] │
├──────┬───────────────────────────────────────────────────────┤
│sidebar(窄图标栏) │ main                                     │
│  市场    │   (见各页面描述)                                   │
│  行情    │                                                     │
│  波动率  │                                                     │
│  策略    │                                                     │
│  期货    │                                                     │
│  异动    │                                                     │
│  期权到期日历 │                                                │
│  ─────  │                                                     │
│  帮助/用户菜单 │                                                │
└──────┴───────────────────────────────────────────────────────┘
```
- 顶栏左侧有 **工作区 tab**（当前"模拟账号"），支持拖拽、`+新建标签`（新建工作区 tab）。顶栏右侧是窗口缩小/放大/关闭。
- 页面路由用 hash：`#/market` 等。

### 2.2 左侧导航（6 主功能 + 3 工具；实测 aria 标签）
| 索引 | aria-label | 页面内容 |
|---|---|---|
| 0 | 市场 | **期权监控面板**：板块tab(全部/股指/金属/能化/农副/油脂/黑色) + 排序面板列表：隐波最大上升、隐波最大下降、波动率溢价最高/最低；另有"仅夜盘"、"外盘"按钮（带渐金跑马灯 = Pro 会员功能） |
| 1 | 行情 | **品种详情**（默认丁二烯橡胶 BR2610）：顶部标的名 + 合约月份链(2610主17天/2611/.../2706)；子tab：行情图表/T型报价/策略优选；行情图表内再分：分时/5日/日线 + 平值隐波/持仓量 |
| 2 | 波动率 | **波动率曲面**：2D/3D 视图 + "叠加历史隐波"开关；表格行=期权月份(2609~2706)，列=期货指标(现值/涨幅) + 平值隐波等；图例"期货/指标"可切换 |
| 3 | 策略 | **策略构建器**：行情表达行(名称/最新价/方向/数量)、行权价选择(C x1 OR P)、添加合约、策略下单、回测模拟；下方显示净支出/最大收益/盈亏平衡/最大亏损/胜率% /预期盈亏等；右侧带 P&L 图(当前价格/目标价/盈亏平衡安安)。右侧显示胜率图、还有"回测模拟"按钮 |
| 4 | 期货 | **期货分析页**：期货价格日线图(开盘/最高/最低/收盘/成交量/平值隐波) + 期货期限结构(今日vs昨日，现值/涨幅) |
| 5 | 异动 | **期权异动榜**：列=期权合约/合约价格/涨幅/剩余时间/标的价格/实虚值%/成交量/成交额/持仓量/昨持仓/增仓量/增仓率/增仓额/买卖比；顶部有板块tab+高级筛选+列配置 |
| 6 | 期权到期日历 | **弹出日历面板**（非独立页）：2026年9月日历，标注各交易所到期日（上期所/能源中心/郑商所/大商所/中金所/广期所/上交所/深交所） |
| 7 | 帮助 | 帮助菜单（未深挖） |
| 8 | 打开用户菜单 | 弹层：未设置昵称/普通账户/开通Pro/积分与权益/个人设置/主题/界面缩放100%/退出登录 |

### 2.3 关键页面细节

**市场/期权监控面板**（当前工作区默认页）
- 板块tab：全部/股指/金属/能化/农副/油脂/黑色；另有"仅夜盘""外盘"（Pro 功能，渐金跑马灯）。
- 排序面板（从左到右）：隐波最大上升（列：名称/涨幅%/隐波变化/分时预览）、隐波最大下降、波动率溢价最高（列：名称/隐波/实波/溢价）、波动率溢价最低。
- 这是采集器 legend text5 解析的页面：每行五行一组（名称/代码/月份/主/涨幅%）。

**自选 tab**（市场页顶部"板块/交易所/自选"内的"自选"）：显示用户自选列表（名称/涨幅%/隐波变化/分时预览），实测品种：燃油/焦煤/苯乙烯/对二甲苯/甲醇/PTA/PVC 等。

**行情页 T 型报价**：有完整表头（看涨: Vega/Theta/Gamma/Delta/成交量/持仓量/隐波/涨幅%/最新价/卖价/买价 | 行权价 | 买价/卖价/最新价/涨幅%/隐波/持仓量/成交量/Delta/Gamma/Theta/Vega | 看跌），但**当行权价行显示为空**（与摘要记录"工作区 T 型报价组件无完整行权价链数据"一致）。
- 行情图表子tab内数据区顶部还有一个迷你指标条："最新价 1XXXX 标的涨幅% 剩余时间 平值隐波 隐波变化 隐波涨速 实波 溢价 偏度 隐波百分位 偏度百分位 走势预览"——该指标条在集合竞价窗口下实时刷新。

**波动率页**：视图模式 2D/3D；表格=月份×指标；"叠加历史隐波"开关（历史叠加）。指标含：期货(现值/涨幅)、平值隐波(指标/数值/变化)、实波、偏度等。

**策略页**：策略构建器文档；操作流程：行权价(最新价 x1) → 选 C/P → 添加合约 → 策略下单/回测模拟。策略卡片：买入看涨期权(买入1手 16000C)、备兑看涨期权(持有标的,卖出1手 16600C) 等；参数：净支出/最大收益/盈亏平衡/最大亏损/预期盈亏/胜率%。

**异动页**：期权合约异动榜；实测样例行：`原油2610 C 700 sc2610C700 16.65 -5.13% 5天 691.521 -1.2% 3.06万 4.94亿 3676 3632 +44 ...`

## 3. 本地文件系统（静态资源/配置）

### 3.1 安装目录 `E:\OpendVlab Legend\openvlab-legend`
- `resources/app.asar`：前端包（React 应用，页面 `dist/index.html`）
- `resources/vlab-td-local/`：**本地 CTP 网关目录**（*本次重要实地发现*）
  - `cfwtd.exe`/`windows/`：CTP 网关二进制
  - `config_simnow.ini`：**上期技术-SimNow-CTP**（broker 9999，td_front `tcp://182.254.243.31:30002`，md_front `tcp://182.254.243.31:30012`；app_id `simnow_client_test`）
  - `config_simnow_24.ini`：上期技术-SimNow-CTP-**盘后-7*24**（td 40001 / md 40011）
  - `product_param.json`：行情/产品白名单参数（`generated_at/source/rows`）
- `*.dll/pak`：Electron + Chromium 运行时

### 3.2 用户数据 `C:\Users\Lenovo\AppData\Roaming\openvlab-legend`
- `app-settings.json`：`{"version":1,"deviceId":"...","window":{"bounds":{"x":120,"y":82,"width":1468,"height":856},"maximized":false}}` —— 窗口信息
- `auth-session.json`、`openvlab-login-credentials.json`(.key)：OpenVlab 云账号登录态
- `ctp-login-credentials.json`(.key)：**AES-256-GCM 加密的 CTP 凭据**（iv/authTag/encryptedPassword）
- `ctp-reverse-position-tasks.json`、`device-id.json`、`legend-data-migration-v2`
- `instrument-cache\openvlab__ctp__instrument-cache__v1__73696d6e6f77__39393939__323730373732.json`：**91 期货 + 91 期权合约元数据缓存**（离线可读，含乘数/报价单位/交易所/productClass）
- `runtime\<pid>\`：每次会话一个目录
  - `.cfwtd_token`：**cfwtd WebSocket token**（本次 pid 33264 → `b1b56dc9993357cae25c3f829e8cc900`；每次登录刷新）
  - `flow\md_<investor>/td_<investor>`：CTP 流文件（**.con** 结算单等）
  - `logs\`：引擎日志
- `logs\cfwtd-*.log`：**cfwtd 启动日志**，含 WebSocket 端口与站点列表

### 3.3 cfwtd 本地网关（实测确认）
- 启动即监听 `127.0.0.1:<动态端口>`（本次 **64239**，随登录变化）
- WebSocket server（WebSocket++/0.8.2 协议栈），**token auth enabled**、空闲 10s 登出
- 支持的站点（logs）：simnow、simnow_24
- 无 token 直连返回 400（`ws://127.0.0.1:64239` 直接用 token 在 query/header 均被拒，认证格式仍在逆向）

## 4. 网络数据链路（重要实测发现）

通过 CDP Network 域观察页面资源加载，确认 **Legend 界面的行情数据来自 OpenVlab 云端 REST API**：

| 端点（均可匿名访问，返回 `{"code":0,"result":...,"message":"ok"}`） | 数据 |
|---|---|
| `GET https://www.openvlab.cn/api/ctamap-all` | **76 品种全期权波动率地图**：sector/sector_alias/product/product_alias/prodUnd/exchange/has_night_trading/exp/rv22/expiry_date/last_time/ctn/price/frontfwd_mom/atmv_current/atmv_percentile/atmv_1dchg ... |
| `GET https://www.openvlab.cn/api/dto/{code}` | **单标的行情**（code 可用品种代码如 SA/MA，或 ETF 如 510050）：返回 headline/events + context.r(1d/7d/14d/30d/91d/183d/274d/365d 收益率) + context.i[] 内每个合约的最新价/买卖/成交量/持仓量/合约代码等 |
| `GET https://www.openvlab.cn/api/volatility-surface/{code}` | **波动率曲面**（按月分键，如 202610/202701/202705/202611）：mktvol_tday_call_bid/ask、theovol_tday/yday、atmvol_tday/yday、forward_td/yd、delta_tday_call/put、strike_oid_c/p、strike_poi_c/p、sum_oi_call/put、rho、valphaT、pdf_list、days_to_expiry、expiry_date、trading_strike、display_strike 等 |
| `GET https://www.openvlab.cn/api/volatility-surface-yday/{code}` | 昨日曲面（**需登录态**，匿名 404） |
| 页面内其他 | `/api/auth/user` `/api/legend/layouts` `/api/features/daily-pro-trial/status` `/api/product-exps` `/api/sector-info` `/api/exchange-info` `/api/watchlist/*` `/api/last-bars` `/api/price-volatility-series`（watchlist 系列需登录态） |

- **观察**：页面平时**不建立到本地 cfwtd 的 WebSocket 连接**（12s 监听无帧），cfwtd 仅在登录/交易链路使用；行情走 REST 轮询（含 pull 各种候选 bar/数据）。

## 5. 学会使用的操作要点（人机操作方式）

1. **启动**：普通双击仅出窗口（无 CDP）。带调试口：`openvlab-legend.exe --remote-debugging-port=9225`（即"Legend 调试模式.bat"）。**已运行实例无法后补 CDP**。
2. **登录**：SimNow 账号密码在首启登录页输入；自动登录可先 CDP 填表提交（项目 legend_ui_collector 已用 `ctp-login-credentials` AES 解密 + CDP 提交实现）。
3. **看行情**：默认"市场"页即期权监控面板；点任意品种行进入"行情"页看合约月份链与 T 型/图表/策略；tab 可拖拽重排；"板块/交易所/自选"切换数据范围。
4. **选合约**：行情页顶部月份链可点选（2610/2611/.../2706）；主连为"X主"。
5. **波动率曲面**：左侧"波动率"→ 2D/3D 切换、叠加历史隐波；点表头切换"期货/指标"。
6. **策略构建**：左侧"策略"→ 选行权价/方向(C/P) → 添加合约 → 策略下单 / 回测模拟。
7. **期权到期日历**：左侧齿轮菜单 → 弹出日历标注各所到期日。
8. **用户菜单**：左下头像 → 个人设置/主题/界面缩放/退出登录。
9. **Pro 功能**（仅夜盘/外盘/大额深度等）：金色跑马灯标注，需开通 Pro。

## 6. 自动化接入点（对采集装置最有价值的部分）

| 方式 | 说明 | 状态 |
|---|---|---|
| CDP:9225 | 接入 `ws://127.0.0.1:9225/devtools/page/...` → Runtime.evaluate 读 DOM/点击/截图 | ✅ 已用 |
| DOM 读取 | 页面文本/表格/导航全可读；`aside button[aria-label]` 定位导航；hash 路由 `#/market` 等 | ✅ 已用 |
| cfwtd WebSocket | 动态端口 + token（`runtime/<pid>/.cfwtd_token`），可作交易/行情推送交叉源 | ⚠️ token 认证格式待解 |
| openvlab REST | 匿名 3 端点（ctamap-all/dto/volatility-surface）免费权威补充数据 | ✅ 实测可用 |
| instrument-cache | 离线 182 合约元数据 | ✅ 可用 |

## 7. 与既有采集器的对应关系

- `legend_ui_collector.py` 的 text5 解析（自选"名称/价格/4位月份/主/涨幅%"五行一组）即"市场页期权监控面板"每行的 DOM 文本结构。
- `selectors.json` 的 `legend_cdp`（当前空占位）可合力扩展为：页面 hash 路由 + 顶部 tab 定位 + 具体表格选择器。
- T 型报价无完整行权价链（实测确认）→ 期权链维持量化侧新浪源；但 **openvlab `/api/volatility-surface` 有按月曲面与 delta/gamma/theta/vega 数据**，可作为期权希腊字母/曲面的免费补充源。