# openvlab.cn 匿名 REST API 数据存档

> 抓取时间：2026-09-06 深夜～07 凌晨 ｜ 抓取工具：`../工具/openvlab_api.py`
> 全部数据来自 https://www.openvlab.cn 匿名公开接口（无需登录），仅用于个人研究。

## 内容

| 文件 | 数量 | 说明 |
|---|---|---|
| `ctamap_all.json` | 1 | **76 品种全期权波动率地图**（sector/sector_alias/product/product_alias/prodUnd/exchange/has_night_trading/exp/rv22/expiry_date/last_time/ctn/price/frontfwd_mom/atmv_current/atmv_percentile/atmv_1dchg/skew_current/skew_percentile/skew_1dchg/valphaT） |
| `dto_*.json` | 76 | 各标的实时行情（headline/events/context.r 多周期收益率/context.i 各合约 最新价·买卖·量仓·代码·乘数·精度·时间戳） |
| `surface_*.json` | 76 | 各标的按月波动率曲面（mktvol_tday_call/put_bid/ask、theovol_tday/yday、atmvol_tday/yday、forward_td/yd、delta_tday_call/put、strike_oid/poi_c/p、sum_oi/poi_call/put、rho、valphaT、pdf_list、days_to_expiry、expiry_date、trading_strike、display_strike、is_ready_fit、move_up/dn、last_time、prior_date） |

品种覆盖：SA/MA/BU/BR/FG/SH/UR/PP/EG/PX/PTA/V/TA/CU/AL/ZN/NI/PB/SN/AU/AG/SC/FU/RB/I/J/JM/JD/L/LC/LG/LH/M/OI/P/PG/PK/PL/PR/PS/RM/RU/SF/SI/SM/SP/SR/C/CF/CJ/CS/A/AD/AO/AP/B/BC/BZ/EB/IM/IF/IH/V/Y/OP 等 + ETF(510050/510300/510500/159901/159915/159919/159922/588000/588080)。

## 复现

```bat
D:\Python\python.exe ..\工具\openvlab_api.py fetch-all
```
（自动抓 ctamap-all + 全品种 dto + surface，0.3s 间隔，约 4 分钟；仅个人研究用，勿高频调用）

## 与装置的关系

- 这三个端点可作为 **Legend/同花顺界面采集之外的免费权威补充数据源**（尤其期权曲面/希腊字母/波动率地图）。
- `run.py` 现有 `--probe`/`--once` 采集的是界面数据；此存档为"数据层直连"方案验证，接入 fusion.py 时可直接解析这些 JSON。
