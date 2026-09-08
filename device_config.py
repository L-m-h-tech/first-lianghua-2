# -*- coding: utf-8 -*-
"""装置配置加载：config.json + 环境变量 + selectors.json（控件定位配置化）。

约定：
- config.json 为唯一手工编辑的装置配置（路径、账号、间隔、告警阈值）；
- selectors.json 存界面控件定位（DOM 选择器 / UIA 控件匹配），软件升级只改这里；
- .env 可覆盖 config.json 中带 FUTURES_MONITOR_ 前缀的标量（同样式同量化项目 config_loader）。
密码只出现在 config.json / .env，绝不打日志。
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
SELECTORS_FILE = BASE_DIR / "selectors.json"
ENV_FILE = BASE_DIR / ".env"

_DEFAULTS = {
    "quant_dir": r"E:\LHsystem\量化\futures_monitor",
    "legend": {
        "exe": r"E:\OpendVlab Legend\openvlab-legend\openvlab-legend.exe",
        "cdp_port": 9225,
        "data_dir": r"E:\OpendVlab Legend\openvlab-legend\openvlab-legend-data",
        "appdata_dir": r"C:\Users\Lenovo\AppData\Roaming\openvlab-legend",
        "credentials_file": "ctp-login-credentials.json",
    },
    "ths": {
        "exe": r"E:\同花顺期货通\bin\happ.exe",
        "notice_xml": r"E:\同花顺期货通\bin\FutureData\Notice.xml",
    },
    "ctp_accounts": [],          # 多账号扩展空间：{"site_id","user_id","password"}，默认空=自动读 Legend 凭据
    "intervals": {
        "probe": 3.0,            # 探测软件是否就绪的间隔（秒）
        "collect": 30.0,         # 在线时主采集间隔（秒）
        "offline": 120.0,        # 离线时低频巡检间隔（秒）
        "status_write": 10.0,    # 状态文件写入间隔（秒）
    },
    "quality": {
        "max_price_jump_pct": 4.0,     # 单次采集价格跳变告警阈值(%)
        "max_staleness_sec": 300,       # 断流告警阈值(秒)
        "conflict_diff_pct": 1.0,       # 与新浪/东财同品种价差告警阈值(%)
        "pcr_lookback_days": 90,
    },
    "http": {
        "serve_host": "127.0.0.1",
        "serve_port": 8790,            # HTML 显示页本地服务端口
    },
}


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_dotenv():
    if not ENV_FILE.exists():
        return {}
    env = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip("\"'")
    except Exception:
        pass
    return env


def _apply_env(cfg, env):
    """FUTURES_MONITOR_* 开头的环境变量覆盖对应标量配置。"""
    for k, v in env.items():
        if not k.startswith("FUTURES_MONITOR_"):
            continue
        path = k[len("FUTURES_MONITOR_"):].lower().split("_")
        # 逐层下钻：FUTURES_MONITOR_QUANT_DIR -> quant_dir；LEGEND_EXE -> legend.exe 等
        node = cfg
        for i, p in enumerate(path):
            if i == len(path) - 1:
                if isinstance(node, dict) and p in node:
                    node[p] = v
            else:
                node = node.get(p)
                if not isinstance(node, dict):
                    break
    return cfg


def load_config():
    cfg = _deep_merge(_DEFAULTS, {})
    if CONFIG_FILE.exists():
        try:
            cfg = _deep_merge(cfg, json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception as e:
            print("[device_config] config.json 解析失败，使用默认值: %s" % e)
    cfg = _apply_env(cfg, _load_dotenv())
    cfg["_base_dir"] = str(BASE_DIR)
    return cfg


def load_selectors():
    if SELECTORS_FILE.exists():
        try:
            return json.loads(SELECTORS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print("[device_config] selectors.json 解析失败: %s" % e)
    return {}


CONFIG = load_config()
SELECTORS = load_selectors()


def quant_dir():
    return CONFIG.get("quant_dir") or _DEFAULTS["quant_dir"]


def data_dir():
    d = Path(CONFIG.get("_base_dir")) / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def status_file():
    return data_dir() / "collector_status.json"


def legend_credentials():
    """多账号扩展：config.json 显式配置优先；否则自动读 Legend 的凭据文件（现成 SimNow 账号）。"""
    if CONFIG.get("ctp_accounts"):
        return CONFIG["ctp_accounts"]
    cred = Path(CONFIG["legend"].get("appdata_dir", "")) / CONFIG["legend"].get("credentials_file", "ctp-login-credentials.json")
    try:
        data = json.loads(cred.read_text(encoding="utf-8"))
        return [{"site_id": data.get("siteId", "simnow"),
                 "user_id": data.get("userId", ""),
                 "password": data.get("password", "")}]
    except Exception:
        return []
