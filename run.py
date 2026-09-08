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
import threading
import time

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


def cmd_daemon(args):
    import legend_ui_collector as L
    import ths_ui_collector as T
    fusion.ensure_quant()
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


def cmd_serve(args):
    import functools
    import http.server
    import urllib.parse
    data_path = device_config.data_dir()
    handler_cls = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(data_path))
    host, port = CONFIG["http"]["serve_host"], CONFIG["http"].get("serve_port", 8790)
    srv = http.server.ThreadingHTTPServer((host, port), handler_cls)
    fusion.LOG.info("显示页服务启动: http://%s:%d/dashboard.html", host, port)
    print("显示页: http://%s:%d/dashboard.html" % (host, port))
    print("状态JSON: http://%s:%d/collector_status.json" % (host, port))
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
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())