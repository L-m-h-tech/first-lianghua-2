# -*- coding: utf-8 -*-
"""界面操作收集装置 入口。

用法（D:\\Python\\python.exe run.py ...）：
  --probe [--legend|--ths]   探测软件界面可读性（实测用，不写库）
  --once                     手动跑一轮采集（写 monitor.db）
  --daemon                   常驻采集（后台线程，写状态文件与 HTML 页）
  --serve                    本地 HTTP 服务（HTML 显示页 + collector_status.json）
  --selftest                 零网络零软件自检（导入 + 解析断言）

说明：
- 本装置不拉起任何软件；请手动打开 Legend（可用『Legend 调试模式.bat』）与同花顺期货通。
- 数据直连量化项目的 monitor.db（WAL 多进程安全），路径见 config.json 的 quant_dir。
"""
import argparse
import json
import os
import re
import threading
import time
from pathlib import Path

import device_config
import fusion
import dashboard
from fusion import StatusHub

CONFIG = device_config.CONFIG


def cmd_probe(args):
    import legend_ui_collector as L
    import ths_ui_collector as T
    status = StatusHub()
    if not args.only:
        L.probe(status)
        print()
        T.probe(status)
        print()
        try:
            import openvlab_collector as O
            O.probe(status)
        except Exception as e:
            print("[OpenVlab] probe 失败: %s" % e)
        print()
        try:
            import jiaoyikecha_collector as J
            J.probe(status)
        except Exception as e:
            print("[jiaoyikecha] probe 失败: %s" % e)
    elif args.only == "legend":
        L.probe(status)
    elif args.only == "ths":
        T.probe(status)
    elif args.only == "openvlab":
        import openvlab_collector as O
        O.probe(status)
    elif args.only == "jiaoyikecha":
        import jiaoyikecha_collector as J
        J.probe(status)
    if args.save_status:
        status.update(alerts=[])
        status.save()


def cmd_once(args):
    import legend_ui_collector as L
    import ths_ui_collector as T
    status = StatusHub()
    fusion.ensure_quant()
    # A3: 每次手动采集前 seed 合约元数据（幂等，从量化保证金/手续费CSV）
    try:
        fusion.seed_ctp_instruments()
    except Exception:
        pass
    r1 = L.collect_cycle(status, L.MinuteAggregator())
    r2 = T.collect_cycle(status)
    r3 = _collect_openvlab(status)
    r4 = _collect_jiaoyikecha(status)
    status.update(coverage=fusion.latest_coverage())
    status.save()
    rep = status.save_report()
    print("[一次采集] legend=%s ths=%s openvlab=%s jiaoyikecha=%s" % (r1, r2, r3, r4))
    print("状态文件: %s" % status.path)
    print("报告文件: %s" % rep)


def _collect_openvlab(status):
    try:
        import openvlab_collector as O
        if device_config.CONFIG.get("openvlab", {}).get("enabled", True):
            return O.collect_cycle(status)
    except Exception as e:
        fusion.LOG.warning("openvlab 采集失败: %s", e)
    return {"quotes": 0, "chains": 0}


def _collect_jiaoyikecha(status):
    try:
        import jiaoyikecha_collector as J
        if device_config.CONFIG.get("jiaoyikecha", {}).get("enabled", True):
            return J.collect_cycle(status)
    except Exception as e:
        fusion.LOG.warning("jiaoyikecha 采集失败: %s", e)
    return {"saved": 0, "items": {}}


def _status_writer(status):
    """后台：周期写 collector_status.json + 检测数据过期。"""
    stop = threading.Event()
    intervals = CONFIG["intervals"]
    max_stale = CONFIG.get("quality", {}).get("max_staleness_sec", 300)

    def run():
        last_alert = 0
        while not stop.is_set():
            try:
                status.update(coverage=fusion.latest_coverage()
                              if _quant_ok() else {})
                # 过期检测：距上次采集超过阈值则告警
                snap = status.snapshot()
                stale = fusion.staleness_seconds(snap.get("updated"))
                if stale is not None and stale > max_stale:
                    now_ts = int(time.time())
                    if now_ts - last_alert > max_stale:
                        status.alert("STALE", "数据已 %.0f 秒未更新（阈值 %ds）" % (stale, max_stale))
                        last_alert = now_ts
                status.save()
                # 同步写量化侧可读文件（report_device.json + reports/device_status.txt），
                # 供量化看板"数据采集装置 / 装置健康详情"页签实时读取。
                status.save_report()
            except Exception as e:
                fusion.LOG.warning("状态写入失败: %s", e)
            stop.wait(intervals["status_write"])

    return run, stop


def _quant_ok():
    try:
        fusion.ensure_quant()
        return True
    except Exception:
        return False


def _cdp_listening(port):
    """探测本地 CDP 端口是否在监听（Legend 调试模式生效的标志）。"""
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1)
        s.close()
        return True
    except OSError:
        return False


_CREATE_NO_WINDOW = 0x08000000

# _launch_software 亲手拉起的进程 PID（退出时联动关闭；已在运行的软件不记录）
_launched_pids = []


def _record_launched(p):
    """记录由本装置拉起的进程（装置退出时联动关闭）。"""
    if p is not None and getattr(p, "pid", None):
        _launched_pids.append(p.pid)


def _shutdown_started():
    """装置退出时关闭本轮拉起的 Legend/同花顺（只杀自己拉起的实例）。"""
    import subprocess as _subprocess
    global _launched_pids
    if not _launched_pids:
        return
    for pid in list(_launched_pids):
        try:
            r = _subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                                creationflags=_CREATE_NO_WINDOW, capture_output=True, timeout=15)
            fusion.LOG.info("装置退出，已关闭由本装置拉起的进程(pid=%d) rc=%s", pid, r.returncode)
        except Exception as e:
            fusion.LOG.warning("关闭装置拉起进程(pid=%d)失败: %s", pid, e)
    _launched_pids = []


def _ensure_ths_debug_mode():
    """确保同花顺期货通 DataCenter.xml 开启 Cef Console 调试开关（幂等、改前备份 .bak）。
    开启后重启 happ.exe 即弹出独立 DevTools 窗口（调试模式）。"""
    cfg = device_config.CONFIG.get("ths", {})
    if not cfg.get("debug_mode", True):
        return
    path = cfg.get("data_center_xml")
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return
    if re.search(r'<Console\b[^>]*\benable="true"', text):
        return  # 已开启，无需写回
    patched = None
    # Console enable=false → true
    patched, n = re.subn(r'(<Console\b[^>]*\benable=")false(")', r'\1true\2', text)
    if not n:
        patched = None
    # 无 Console → 在 <Cef> 块内首部插入
    if not patched:
        m = re.search(r"(<Cef\b[^>]*>)(.*?)(</Cef>)", text, re.S)
        if m:
            lead = '\n      ' if '\n' in m.group(2) else ' '
            patched = m.group(1) + lead + '<Console enable="true"/>' + m.group(2) + m.group(3)
    if not patched:
        fusion.LOG.warning("同花顺 DataCenter.xml 结构异常，未修改调试开关")
        return
    try:
        bak = path + ".bak"
        if not os.path.exists(bak):
            import shutil
            shutil.copy2(path, bak)
        nl = "\r\n" if "\r\n" in text else "\n"
        with open(path, "w", encoding="utf-8", newline=nl) as f:
            f.write(patched)
        fusion.LOG.info("已开启同花顺调试模式（DataCenter.xml Cef Console=true，原文件备份 %s）", bak)
    except OSError as e:
        fusion.LOG.warning("写入同花顺 DataCenter.xml 失败: %s", e)


def _launch_software():
    """daemon 启动前检查并拉起 Legend（调试模式）与同花顺期货通（调试模式）。
    Legend 以 CDP 9225 是否监听为准、同花顺以调试开关+重启为准：进程在跑但未开启
    调试都结束并重启；用 SW_SHOWNOACTIVATE 避免窗口抢焦点。"""
    import subprocess, ctypes

    SW_SHOWNOACTIVATE = 4
    CREATE_NO_WINDOW = 0x08000000
    si = subprocess.STARTUPINFO()
    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_SHOWNOACTIVATE

    def _is_running(name_part):
        """简单判断进程是否存在（tasklist 按名称片段匹配）。"""
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq %s" % name_part],
                creationflags=CREATE_NO_WINDOW, text=True)
            return name_part.lower() in out.lower()
        except Exception:
            return False

    # Legend（调试模式，CDP 9225）—— 幂等以端口为准，而非进程
    legend_exe = device_config.CONFIG["legend"]["exe"]
    if _cdp_listening(9225):
        fusion.LOG.info("Legend CDP 9225 已就绪，跳过启动")
    elif Path(legend_exe).exists():
        need_restart = _is_running("openvlab-legend.exe")
        restart_debug = device_config.CONFIG.get("legend", {}).get("restart_debug", True)
        if need_restart and restart_debug:
            try:
                subprocess.run(["taskkill", "/IM", "openvlab-legend.exe", "/F"],
                               creationflags=CREATE_NO_WINDOW, capture_output=True, timeout=30)
                fusion.LOG.info("Legend 已运行但无调试口，已结束旧实例")
                time.sleep(2)
                need_restart = False
            except Exception as e:
                fusion.LOG.warning("结束 Legend 旧实例失败（保持现状）: %s", e)
                restart_debug = False
        if not need_restart:
            try:
                p = subprocess.Popen(
                    [legend_exe, "--remote-debugging-port=9225", "--remote-allow-origins=*"],
                    startupinfo=si)
                _record_launched(p)
                fusion.LOG.info("自动拉起 Legend 调试模式")
            except Exception as e:
                fusion.LOG.warning("Legend 启动失败: %s", e)
        else:
            fusion.LOG.info("Legend 无调试口且开关关闭或结束失败，保持现状")
    else:
        fusion.LOG.warning("Legend exe 未找到: %s", legend_exe)

    # 同花顺期货通（调试模式）：先确保 DataCenter.xml 调试开关，进程在跑则重启应用
    ths_exe = device_config.CONFIG["ths"]["exe"]
    if Path(ths_exe).exists():
        _ensure_ths_debug_mode()
        need_restart = _is_running("happ.exe")
        restart_debug = device_config.CONFIG.get("ths", {}).get("restart_debug", True)
        if need_restart and restart_debug:
            # 进程在跑（可能为普通模式）→ 重启以应用调试开关
            try:
                subprocess.run(["taskkill", "/IM", "happ.exe", "/F"],
                               creationflags=CREATE_NO_WINDOW, capture_output=True, timeout=30)
                fusion.LOG.info("同花顺期货通已运行，已结束旧实例准备以调试模式重启")
                time.sleep(2)
                need_restart = False
            except Exception as e:
                fusion.LOG.warning("结束同花顺旧实例失败（保持现状）: %s", e)
                restart_debug = False
        if not need_restart:
            try:
                p = subprocess.Popen([ths_exe], startupinfo=si)
                _record_launched(p)
                fusion.LOG.info("自动拉起同花顺期货通调试模式")
            except Exception as e:
                fusion.LOG.warning("同花顺启动失败: %s", e)
        else:
            fusion.LOG.info("同花顺期货通已运行（重启开关关闭或结束失败），保持现状")
    else:
        fusion.LOG.warning("同花顺 exe 未找到: %s", ths_exe)


def cmd_daemon(args):
    import legend_ui_collector as L
    import ths_ui_collector as T
    fusion.ensure_quant()
    # A3: 常驻启动前 seed 合约元数据（幂等，从量化保证金/手续费CSV）
    try:
        fusion.seed_ctp_instruments()
    except Exception:
        pass
    # 自动拉起 Legend（调试模式）与同花顺期货通（调试模式，已有进程则跳过/重启，不抢焦点）
    try:
        _launch_software()
    except Exception as e:
        fusion.LOG.debug("自动拉起软件失败: %s", e)
    status = StatusHub()
    stop = threading.Event()
    agg = L.MinuteAggregator()
    threads = [
        threading.Thread(target=L.loop, args=(status, agg, stop), daemon=True),
        threading.Thread(target=T.loop, args=(status, stop), daemon=True),
    ]
    if device_config.CONFIG.get("openvlab", {}).get("enabled", True):
        import openvlab_collector as O
        threads.append(threading.Thread(target=O.loop, args=(status, stop), daemon=True))
    if device_config.CONFIG.get("jiaoyikecha", {}).get("enabled", True):
        import jiaoyikecha_collector as J
        threads.append(threading.Thread(target=J.loop, args=(status, stop), daemon=True))
    writer, _ = _status_writer(status)
    threads.append(threading.Thread(target=writer, daemon=True))
    for t in threads:
        t.start()
    dashboard.write_dashboard(dashboard.collect_dashboard_data(status))
    fusion.LOG.info("装置常驻启动（Ctrl+C 结束）")
    print("装置常驻运行中。HTML 页: http://%s:%d/dashboard.html" %
          (CONFIG["http"]["serve_host"], CONFIG["http"]["serve_port"]))
    print("如需启动显示页服务，另开窗口运行: D:\\Python\\python.exe run.py --serve")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        _shutdown_started()   # 联动关闭本装置拉起的 Legend/同花顺


def cmd_serve(args):
    import functools
    import http.server
    import urllib.parse
    data_path = device_config.data_dir()
    # C2（协同）：把量化 reports 目录挂载为 /quant/ 前缀，供 dashboard 读取
    # 量化报告（latest_report.txt / signals.csv）。
    try:
        quant_report_dir = str(
            Path(device_config.quant_dir()) / "reports")
    except Exception:
        quant_report_dir = ""

    class DeviceHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(data_path), **kw)

        def translate_path(self, path):
            if quant_report_dir and path.startswith("/quant/"):
                rel = urllib.parse.unquote(path[len("/quant/"):])
                return str(Path(quant_report_dir) / rel)
            return super().translate_path(path)

        def log_message(self, fmt, *args):
            fusion.LOG.debug("serve %s", fmt % args)

    host, port = CONFIG["http"]["serve_host"], CONFIG["http"].get("serve_port", 8790)
    srv = http.server.ThreadingHTTPServer((host, port), DeviceHandler)
    fusion.LOG.info("显示页服务启动: http://%s:%d/dashboard.html", host, port)
    print("显示页: http://%s:%d/dashboard.html" % (host, port))
    print("状态JSON: http://%s:%d/collector_status.json" % (host, port))
    if quant_report_dir:
        print("量化报告: http://%s:%d/quant/latest_report.txt" % (host, port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


def cmd_selftest(args):
    """离线自检：导入各模块 + 关键解析函数手写断言。"""
    ok = 0
    failed = []

    def check(name, fn):
        nonlocal ok
        try:
            fn()
            ok += 1
            print("  PASS %s" % name)
        except Exception as e:
            failed.append((name, str(e)))
            print("  FAIL %s: %s" % (name, e))

    import ui_collector as U
    import legend_ui_collector as L
    import ths_ui_collector as T
    import fusion as F

    check("ui_collector.parse_tsv", lambda: (
        (lambda t: (t and t["columns"] == ["a", "b"]))(U.parse_tsv("a\tb\n1\t2\n"))))
    check("ui_collector.normalize_number", lambda: U.normalize_number("1,234.5") == 1234.5)
    check("legend.parse_quote_row", lambda: L.parse_quote_row(
        ["名称", "最新价"], ["铜", "70000"], {"price": {"name": "最新价"}})["price"] == "70000")
    check("legend.MinuteAggregator", lambda: (lambda a, b: a is not None)(
        *L.MinuteAggregator().aggregate(
            {"code": "cu2610", "price": 1, "ts": "2026-09-06 10:00:00"})))
    check("legend.parse_option_leg", lambda: L.parse_option_leg("cu2610C75000")["strike"] == 75000.0)
    check("ths.parse_notice_xml", lambda: len(
        T.parse_notice_xml("<NoticeInfo><BrokerNoticeList><BrokerNotice><BrokerNo>测试</BrokerNo>"
                           "<NoticeList><Notice><NoticeDate>20260901</NoticeDate>"
                           "<Content>&lt;p&gt;你好&lt;/p&gt;</Content></Notice></NoticeList>"
                           "</BrokerNotice></BrokerNoticeList></NoticeInfo>")["notices"]) == 1)
    check("ths.parse_quote_tsv", lambda: T.parse_quote_tsv(
        ["最新价", "名称"], ["3756", "螺纹钢"])["price"] == "3756")
    check("fusion.check_neg_spread", lambda: F.check_neg_spread(10.5, 10.2)[0] is False)
    check("dashboard.render_html", lambda: "<!DOCTYPE html>" in dashboard.render_html({"quotes": []}))
    check("device_config.legend_credentials", lambda: isinstance(
        device_config.legend_credentials(), list))
    try:
        import openvlab_collector as O
        check("openvlab.parse_ctamap", lambda: len(
            O.parse_ctamap_rows([{"prodUnd": "SA", "product_alias": "纯碱",
                                  "atmv_current": "39.6", "price": "1078"}])) == 1)
        check("openvlab.parse_surface_legs", lambda: (lambda c, p: len(c) == 1 and len(p) == 0)(
            *O.parse_surface_legs({"202610": {"strike_poi_c": '{"1100.0": 10}'}},
                                  exp="202610", code="SA")))
    except ImportError:
        print("  SKIP openvlab（依赖缺失）")
    try:
        import jiaoyikecha_collector as J
        check("jykc.parse_warehouse_receipts", lambda: (
            (lambda o: o and o[0]["value"]["total_vol"] == 134546)(
                J.parse_warehouse_receipts(
                    [{"name": "螺纹钢", "total_vol": 134546, "total_chge": 0,
                      "total_vol2": 13454.6, "chge_rate": 0}]))))
        check("jykc.parse_longhu", lambda: (
            (lambda o: o and o[0]["value"]["longhu"] > 80)(
                J.parse_longhu([{"name": "沪金", "code": "au2612", "longhu": 82.81}]))))
        check("jykc.parse_hg", lambda: (
            (lambda o: o and o[0]["value"]["current_price"] == 16580)(
                J.parse_hg([{"variety": "20号胶", "code": "nr2611",
                             "current_price": 16580, "time": "23:00:00",
                             "min15": "<span class=win>偏多</span>，支撑：16115-16145"}]))))
        check("jykc.parse_net_positions", lambda: (
            (lambda o: o and o[0]["value"]["net_position"] == 600)(
                J.parse_net_positions(
                    [{"broker": "上海中期", "net_position": 600, "net_position_chge": 270}],
                    variety="螺纹钢"))))
    except ImportError:
        print("  SKIP jiaoyikecha（依赖缺失）")

    print("自检 %d/%d 通过" % (ok, ok + len(failed)))
    if failed:
        print("失败项:")
        for name, err in failed:
            print("  - %s: %s" % (name, err))
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="界面操作收集装置")
    ap.add_argument("--probe", action="store_true", help="探测软件界面可读性")
    ap.add_argument("--once", action="store_true", help="手动跑一轮采集")
    ap.add_argument("--daemon", action="store_true", help="常驻采集")
    ap.add_argument("--serve", action="store_true", help="启动 HTML 显示页服务")
    ap.add_argument("--selftest", action="store_true", help="离线自检")
    ap.add_argument("--legend", dest="only", action="store_const",
                    const="legend", help="--probe 仅 Legend")
    ap.add_argument("--ths", dest="only", action="store_const",
                    const="ths", help="--probe 仅同花顺")
    ap.add_argument("--openvlab", dest="only", action="store_const",
                    const="openvlab", help="--probe 仅 OpenVlab REST 数据源")
    ap.add_argument("--jiaoyikecha", dest="only", action="store_const",
                    const="jiaoyikecha", help="--probe 仅 jiaoyikecha 交易可查 REST 数据源")
    ap.add_argument("--save-status", action="store_true",
                    help="--probe 后写 collector_status.json")
    args = ap.parse_args()

    if args.probe:
        return cmd_probe(args)
    if args.once:
        return cmd_once(args)
    if args.daemon:
        return cmd_daemon(args)
    if args.serve:
        return cmd_serve(args)
    if args.selftest:
        return cmd_selftest(args)
    # PyCharm 直接点运行不传参数：默认进入 daemon 模式（Ctrl+C 或停止按钮退出）
    return cmd_daemon(args)


if __name__ == "__main__":
    raise SystemExit(main())