# -*- coding: utf-8 -*-
"""采集器公共循环基座：提取 legend/ths/openvlab/jiaoyikecha 四个 collector 共享的 loop 模式。"""
import threading
import logging


def run_collector_loop(name, collect_fn, status, stop=None, intervals=None,
                       detect_fn=None, logger=None):
    """通用采集器常驻循环。

    Args:
        name: 采集器名称（用于日志）
        collect_fn: 采集函数，签名 collect_fn(status) -> dict
        status: StatusHub 实例
        stop: threading.Event，为 None 则新建
        intervals: dict，需含 "collect" 和 "offline" 键（秒）
        detect_fn: 可选探测函数 detect_fn(status) -> (mode, ...)；
                   若提供，mode=="offline" 时用 offline 间隔
        logger: 可选 logging.Logger，为 None 则用 logging.getLogger(name)
    """
    stop = stop or threading.Event()
    log = logger or logging.getLogger(name)
    intervals = intervals or {"collect": 10, "offline": 60}
    log.info("%s 采集线程启动", name)
    online = True
    while not stop.is_set():
        try:
            if detect_fn:
                mode, _, _ = detect_fn(status)
                if mode == "offline":
                    if online:
                        log.info("%s 离线，转为低频巡检", name)
                        online = False
                    stop.wait(intervals["offline"])
                    continue
                online = True
            result = collect_fn(status)
            status.increment("collections")
            log.info("%s 采集: %s", name, result)
            wait_key = "collect"
            if isinstance(result, dict) and result.get("level") == "offline":
                wait_key = "offline"
            stop.wait(intervals[wait_key])
        except Exception as e:
            log.warning("%s 采集异常: %s", name, e)
            stop.wait(intervals["offline"])
