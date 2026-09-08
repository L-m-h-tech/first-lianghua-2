# 软件学习探索（认识 OpenVlab Legend + 同花顺期货通）——穷尽版

> 本文件夹存放对两台软件的**穷尽式认识 + 全部界面操作学会**的学习成果。
> 两台软件所有界面、功能、交互均已逐层实测并记录；顶层结论见 `../上下文摘要.md`。
> **最新追加：2026-09-08 第二轮实时探索验证**（CDP+UIA 实操），见各子目录补充文件。

## 目录

| 路径 | 内容 |
|---|---|
| [01_Legend/OpenVlab_Legend_学习笔记.md](01_Legend/OpenVlab_Legend_学习笔记.md) | Legend 完整学习笔记（含穷尽探索：T型报价 Canvas/策略优选/CTP 下单面板/Pro 功能清单；§8 功能→位置速查索引） |
| [01_Legend/Legend_实时探索_20260908.md](01_Legend/Legend_实时探索_20260908.md) | **[新]** 2026-09-08 CDP 实时探索：v0.0.98 五大页面完整数据/用户菜单/策略构建器字段/异动榜样例 |
| [01_Legend/元素地图/](01_Legend/元素地图/) | 30+ 份页面元素地图 JSON（每页所有按钮/tab/文本+坐标） |
| [01_Legend/页面DOM归档/](01_Legend/页面DOM归档/) | 各导航页 DOM 文本+表格 dump |
| [02_同花顺/同花顺期货通_学习笔记.md](02_同花顺/同花顺期货通_学习笔记.md) | 同花顺完整学习笔记（12 分类主导航/多品种同列/板块同列/板块管理/交易登录窗口/速查索引） |
| [02_同花顺/同花顺_实时探索_20260908.md](02_同花顺/同花顺_实时探索_20260908.md) | **[新]** 2026-09-08 UIA 实时操作：400+元素树结构/多品种同列实测/板块同列实测/AutomationId 发现 |
| [03_调研资料/联网调研汇总.md](03_调研资料/联网调研汇总.md) | GitHub/CSDN/官网调研结论 |
| [03_调研资料/openvlab_api_存档/](03_调研资料/openvlab_api_存档/) | 76 品种 openvlab 匿名 REST 数据（dto+surface+ctamap，153 文件 11.7MB）+ README |
| [04_截图归档/](04_截图归档/) | 两台软件界面截图 29 张（Legend 12 + 同花顺 17） |
| [工具/](工具/) | cdp_explore.py / legend_map.py / explore_nav.py / enum_ui.py / openvlab_api.py / cdp_explore_v2.py / explore_ths_v2.py |

## 穷尽探索要点（详细见笔记）

**Legend（Electron, CDP:9225）**
- 6 导航 + 弹层全覆盖；行情页 3 子 tab（Radix Tabs data-state 机制已破解：需完整鼠标事件切换）。
- **T 型报价 = Canvas 渲染期权链**（DOM 不可读、OCR 可读）——修正"无完整行权价链"旧结论。
- 策略优选观点→策略映射（极度看跌→熊市价差族、不涨不跌→铁蝶/跨式族、大涨大跌→宽跨式/反向铁蝶族）已全录。
- 右侧工具栏：波动率曲面/持仓排名/下单侧边栏；CTP 下单面板全字段已录。
- Pro 功能清单：仅夜盘/外盘/3D曲面/完整期限图表。

**同花顺期货通（WPF, UIA）**
- 顶部 12 分类主导航 + 5 个次 tab（自选/自选板块/多品种同列/板块同列/最近浏览）全覆盖。
- 多品种同列 = 2x2 四窗格（每格独立周期 radio）；板块同列 = 2/4/6/9 图 + 板块组。
- 板块管理弹窗（新建/导入/添加/删除）+ 期货户交易登录窗口（银河期货_CTP 等）全字段已录。
- 行情表格 FieldGrid 自绘：UIA 不可读、OCR 可读（17 只自选品种实测）。

## 工具用法速查

```bat
:: Legend
D:\Python\python.exe 工具\cdp_explore.py dump|tree|menu|eval "<js>"|click <sel>|snap <png>
D:\Python\python.exe 工具\legend_map.py <out.json>       :: 当前页全元素地图
D:\Python\python.exe 工具\explore_nav.py                 :: 遍历全部导航 dump
:: 同花顺
D:\Python\python.exe 工具\shot.py out.png left,top,right,bottom
:: openvlab 数据
D:\Python\python.exe 工具\openvlab_api.py fetch-all
```
