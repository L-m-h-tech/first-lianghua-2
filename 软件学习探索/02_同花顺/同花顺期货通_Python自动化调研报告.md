# 同花顺期货通 Python 自动化 联网调研报告

> 调研日期：2026-09-09 ｜ 目的：为「未来用 Python 操作同花顺期货通进行实盘交易」项目选型铺路。
> 调研方式：GitHub 仓库检索 + GitHub API 验证 + 搜索引擎（中文技术社区：CSDN/51CTO/博客园/B站）+ 官方文档。
> 结论先行：**同花顺期货通客户端本身不提供公开的 CTP/下单 API**（第三方案例确认"不能执行全自动量化策略，偏向条件单/网格/算法单半自动"），因此自动化的现实路径只有四条：① UI 自动化（pywinauto/uiautomation）；② 绕过期货通、走券商 CTP 直连（vnpy_ctp/openctp）；③ 剪贴板/OCR 数据提取（只读监控）；④ iFinD 数据 API（只拿数据不下单）。
> 补充（同日实测）：**本项目已用 Python `uiautomation` 对已登录模拟账户完成全交易界面实测**——8 个交易页签 DataGrid AutomationId 全集、全部列头字典、下单面板控件、交易设置面板、条件单创建窗均已拿到（详见《同花顺期货通_完全学习手册.md》v3.0），方案①的技术可行性已在本机验证通过。

---

## 0. 实测验证对选型的强化结论（2026-09-09 补充）

以下为本次实测对调研结论的落地验证：

1. **uiautomation 直连可行**：`py -3.12` + `uiautomation` 库已成功连接运行中的同花顺期货通窗口（pid 定位），读取 8 个交易页签全部数据表格。
2. **DataGrid AutomationId 全集（读表金钥匙）**：`QryPositionControl`(持仓) / `QryOpenOrderWidget`(挂单) / `QryExecOrderWidget`(行权) / `QryOrderControl`(委托) / `QryTradeControl`(成交) / `QryCondOrderWidget`(条件单) / `QryStopOrderWidget`(损盈) / `QryContractWidget`(合约)——比社区"读网格控件"的模糊方案精确得多。
3. **完整列头字典**：持仓23列（含期权 Delta/Gamma/Rho/Theta/Vega）、委托13列、成交11列、条件单14列、损盈12列、行权8列、合约18列（费率/保证金/交割日）——Python 解析字段完全明确，无需猜列。
4. **⚠️ 关键坑：下单按钮"买多/卖空/平仓"是 TextControl 而非 ButtonControl**——不能按 Button 类型查找；实测坐标 (666,1266)/(826,1266)/(988,1266)。
5. **模拟账户验证闭环前置条件已备齐**：资金/盘口/合约信息卡 UIA 可读；下单面板品种/手数/价格输入框可 SetValue；"≤N"手数上限提示可读作风控。
6. **控件定位方式优先级**：AutomationId > Name > 坐标。交易页签 tab 无 AutomationId（用 Name/坐标），表格有 AutomationId（直接 FindControl）。

## 0.1 调试模式实测结论（2026-09-10 补充）

- **同花顺期货通存在官方调试模式**：`bin\workspace\DataCenter.xml` 的 `<Debug><Cef><Console enable="true"/></Cef>`，保存后重启 happ.exe 即弹出**独立 DevTools 窗口**（CefBrowserWindow，Chromium 开发者工具全套面板）
- **DevTools 可用于抓内嵌网页流量**（Network 面板实时请求：get-recommend-query、统计接口等）→ 是 Python 自动化读取网页侧数据的**加分通道**（非必需）
- **CDP 远程端口不可用**：`--remote-debugging-port` / `CHROMIUM_FLAGS` 均无效（调试以 DevTools 窗口而非 TCP 端口形式提供）
- **⚠️ UIA 注意**：调试模式开启后 happ 有双顶层窗口（主窗口 + DevTools），uiautomation 按 PID 枚举须按 Name 含"同花顺"定位主窗口
- **结论**：行情/交易数据自动化仍以 UIA 为主通道；调试模式（DevTools）作为内嵌网页排查/抓包辅助，无需依赖 CDP 破解

## 0.2 深度实测补充结论（2026-09-10，v4.0）

1. **搜索＝键盘精灵**：`Alt+W` 打开键盘精灵 → 输入代码 → Enter → 直达合约（已验证 jm2701 跳转）。Python 可 `SendKeys("{Alt}w")+代码+Enter` 程序化跳转。
2. **本地配置金矿**（离线可读）：`users\<账号>\` 下有自选股(SelfStockV3.txt)、完整热键表(MyHotKey.xml：F1-F10/60-83排名/Alt+Z老板键/Alt+W键盘精灵)、键盘交易快捷键(KeyBoradTrade.xml：一键平仓/反手/锁仓/撤单)、个人设置(老板键/交易锁定)、K线图表配置(ChartConfig.json)、账户历史(history_account_config.json：3家券商API)、结算库(Settlement.db 6表：资产/持仓/成交/平仓/账户/银期)——**Python 可离线做数据/配置/对账**。
3. **code.db 深度**：38520 行覆盖国内全品种+外盘(CL/GC/S/NK)+跨期套利(SPD/SP)+期权T型链(JMO/AUO购沽+执行价)+连续/主连(7777/9999)+VIX合约。
4. **板块管理窗口**：标准 WPF ListView，左侧板块列表+右侧品种库（23个连续+主力合约对），支持 新建/添加/导入/删除/编辑。
5. **云端止损开仓**：快捷下单"止损开仓"→ 弹窗设止损止盈触发价+委托价 → 成交后自动生成**云端止损单，软件关闭仍有效**——Python 可创建后托管。
6. **调试模式已开**：`DataCenter.xml` `<Cef><Console enable="true"/>` → 独立 DevTools 窗口（可抓内嵌网页流量）；注意 happ 双窗口（主窗口+DevTools），uiautomation 须按 Name 含"同花顺"定位主窗口。
7. **行情/交易数据自动化主通道仍是 UIA**（§0 已验证），本批发现强化了"客户端内操作完全可行"的结论。

---

## 1. 路线总览

| 路线 | 下单执行 | 读持仓/资金 | 登录 | 可靠性 | 适用 |
|---|---|---|---|---|---|
| **① UI 自动化**（uiautomation/pywinauto） | ✅ | ✅（网格解析/剪贴板） | ✅（验证码需处理） | 中（客户端升级会破坏选择器） | **唯一能直接操作期货通本身的方式** |
| **② CTP 直连**（vnpy_ctp / openctp / TqSdk） | ✅ 最强 | ✅ API 原生回调 | 券商柜台（穿透式认证） | 高（低延迟、结构化） | **实盘生产首选**（绕开期货通） |
| **③ 剪贴板/OCR** | ❌ | ✅ 个股网格 | — | 中 | 只监控不下单 |
| **④ iFinD API** | ❌ | 数据 | 付费 iFinD 账号 | 高 | 只拿行情数据 |

---

## 2. 路线①：UI 自动化（对本项目最直接）

### 2.1 easytrader（同花顺系自动化的事实标准，偏股票）
- https://github.com/shidenggui/easytrader （10.1k stars）— 用 pywinauto 模拟操作同花顺**股票/通用**客户端。
- 仓库结构：`clienttrader.py`（基类）、`universal_clienttrader.py`（同花顺通用版 1.8KB）、各券商版（gf/gj/ht/yh/wk）、`pop_dialog_handler.py`（弹窗/验证码处理）、`remoteclient.py`（远程）。
- ⚠️ 社区反馈（B站"同花顺python自动化交易接口-easytrader"）：**库维护不及时**，客户端 UI 更新常破坏选择器。
- ⚠️ 无期货内置支持；但**模式可复制**：连接已登录客户端 → 定位窗口 → 操作按钮/输入框。

### 2.2 同花顺自动交易专项项目（GitHub）
| 项目 | 星数 | 说明 | 相关度 |
|---|---|---|---|
| crazyAttributor/ths-auto-trade | 26 | 同花顺交易统一版自动下单买卖工具 | ⭐⭐⭐ |
| lantian555666/ths_auto_trade | 25 | 同花顺 trade + 通达信指标程序化交易 | ⭐⭐ |
| Fryt1/Frytrader | 21 | easytrader 分支，**解决同花顺客户端验证码** | ⭐⭐⭐(登录) |
| jaysinco/RobotTrader | 12 | 通过同花顺平台模拟盘策略测试 | ⭐⭐ |
| mclamee/AutoTrader | 7 | THS 交易软件自动交易器 | ⭐ |
| sakuraayase9/ths-auto-trading | 1 | 同花顺模拟盘自动交易（Hermes agent，2026） | ⭐ |
| Coolister-Ye/quant-trading-system | 7 | 同花顺 macOS 原子自动化（atomacos+pyautogui） | ⭐(MAC) |
| zetatez/evolving | 80 | macOS AppleScript 同花顺自动化引擎 | ⭐(MAC) |

### 2.3 核心库：uiautomation（本项目已实测验证 ✅）
- https://github.com/yinkaisheng/Python-UIAutomation-for-Windows
- 安装：`pip install uiautomation`（本项目 Python 3.12 已装并**成功连接到同花顺期货通**）。
- 本项目实测结论（见《同花顺期货通完全学习手册》）：交易窗口的 **tab/按钮/输入框/资金/持仓/盘口全部可用 UIA 定位与读取**，且发现了大量 AutomationId。
- 社区经验：期货通 UI 树部分虚拟化，个别控件需坐标/ClassName 兜底 → **uiautomation 遍历 + pywinauto 坐标点击组合**常见。

### 2.4 教程/文章（CSDN/51CTO/B站）
- CSDN《散户如何实现自动化交易下单——篇1：体系介绍与获取同花顺资金账户和持仓信息》（2024）→ 已明确用 pywinauto 读资金/持仓。
- 51CTO《同花顺期货通PC版 PYTHON》（2023-12）→ 模拟登录期货通 → 取行情 → 下单。
- 51CTO《python pywinauto 控制同花顺下单》（2023-09）。
- B站《python量化交易之同花顺通用客户端自动化下单程序极简版》→ 买入/卖出/撤单三操作。
- B站《同花顺python自动化交易接口-easytrader》（附维护警告）。

### 2.5 登录自动化要点
- **不要每次重新登录**：`Application().connect()` 接住已登录实例，避开验证码。
- 验证码：Frytrader 分支自动处理；easytrader `pop_dialog_handler.py` 是参考实现。
- 券商通道选择（期货通要选具体期货公司通道，如银河/华泰）+ 动态口令是易碎点。

---

## 3. 路线②：CTP 直连（实盘生产首选，绕开期货通）

- **vnpy_ctp**：https://github.com/vnpy/vnpy_ctp — CTP 6.7.11 交易接口，穿透式实盘/评测/模拟三环境，`pip install vnpy_ctp`。
- **vnpy_mini**：https://github.com/vnpy/vnpy_mini — CTP MINI 接口。
- **❌ 关键负面结论**：GitHub 搜索 `vnpy THS gateway`/`同花顺 gateway` **零结果——vnpy 生态不存在同花顺 gateway**。常见误解，勿再找。同花顺必须 UI 自动化，CTP 必须对你自己的券商。
- **openctp**：https://github.com/openctp/openctp （2.9k stars）+ openctp-ctp-python（211 stars）— CTPAPI 兼容多柜台 + **TTS 7×24 模拟环境**（全品种期货期权+A股），可当 Simnow 替代品做策略回测/仿真。
- **Simnow**：https://www.simnow.com.cn — 上期技术官方 CTP 仿真，免费注册，vnpy_ctp `SIMNOW` 通道。
- **TqSdk（天勤）**：https://github.com/shinnytech/tqsdk-python — 依赖快期/部分期货公司服务，不经期货通。

**决策建议**：实盘上量、低延迟、结构化取持仓/资金 → CTP（前提是券商给 CTP 地址）；只在客户端内操作、跟单、低频信号转发 → UI 自动化。

---

## 4. 路线③：剪贴板/OCR（数据读取补充，本项目采集装置已有）

- 社区共识：**聚焦网格 + Ctrl+A/Ctrl+C 剪贴板解析** 是拿精确数字的首选（比 OCR 稳）。
- 本项目 ths_ui_collector.py 已实现"UIA → 剪贴板 → OCR"三级 + Notice.xml 公告 + code.db 字典，与调研结论一致。

---

## 5. 路线④：iFinD 官方数据接口

- **HiThink-Tech/Financial-API**（2.9k stars）：同花顺官方数据服务（实时/历史/财务/板块/涨停），API/MCP/CLI/Python。
- **iFinDPy**（pypi）：`THS_iFinDLogin` / `THS_DataPool` / `THS_HQ` 等；**需付费 iFinD 终端账号**；只做行情数据，不下单。
- **vnpy_ifind**（63 stars）：VeighNa 的 iFinD 数据接口，覆盖期货+期货期权（中金所/上期/大商/郑商）。
- 注意：**"Hevo 协议"是误传**——公开资料中不存在 Hevo 交易协议，"hevo"仅见于同花顺远航版组件名（hevoinstall）。**勿在 Hevo 上投入逆向**（合规风险且我实测的本地行情链路确是私有不公开加密）。

---

## 6. 最佳实践 / 踩坑清单

1. 客户端升级会破坏 UI 选择器 → Python 项目落地时用 `uiautomation` 控件树 dump 复查（我们已写好 `ths_uia_dump.py` 可复用）。
2. 登录验证码 + 券商通道选择是最脆弱的两个点 → 尽量"登录后连接"而非每次重登。
3. 网格数据剪贴板 > OCR。
4. 下单前关掉/处理二次确认弹窗（easytrader `pop_dialog_handler` 是参考）。
5. 先用模拟盘验证：同花顺模拟账户（当前 1813411165）跑 UI 自动化闭环；策略逻辑用 openctp TTS 7×24 或 Simnow 验证。
6. 实盘真正上量：优先向券商申请 CTP 直连（vnpy_ctp），把同花顺 UI 自动化作为客户端内兜底。

---

## 7. 关键资料链接

- easytrader: https://github.com/shidenggui/easytrader
- ths-auto-trade: https://github.com/crazyAttributor/ths-auto-trade
- Frytrader(验证码): https://github.com/Fryt1/Frytrader
- uiautomation: https://github.com/yinkaisheng/Python-UIAutomation-for-Windows
- vnpy_ctp: https://github.com/vnpy/vnpy_ctp ／ vnpy_mini: https://github.com/vnpy/vnpy_mini
- openctp: https://github.com/openctp/openctp ／ https://www.openctp.cn
- Simnow: https://www.simnow.com.cn
- iFinD 官方: https://github.com/HiThink-Tech/Financial-API ／ iFinDPy: https://pypi.org/project/iFinDPy/
- vnpy_ifind: https://github.com/vnpy/vnpy_ifind