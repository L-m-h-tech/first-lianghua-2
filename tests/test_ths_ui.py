# -*- coding: utf-8 -*-
"""ths_ui_collector 解析纯函数单测：零网络、零软件。"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ths_ui_collector as T


SAMPLE_XML = """<?xml version="1.0" encoding="utf-16"?>
<NoticeInfo>
  <LastClearDate>20260401</LastClearDate>
  <LastLoginList>
    <LastLoginInfo><LastLoginDate>20260807</LastLoginDate><LastLoginAccount>8118038291</LastLoginAccount></LastLoginInfo>
    <LastLoginInfo><LastLoginDate>20260413</LastLoginDate><LastLoginAccount>20511797</LastLoginAccount></LastLoginInfo>
  </LastLoginList>
  <BrokerNoticeList>
    <BrokerNotice>
      <BrokerNo>模拟交易</BrokerNo>
      <NoticeList />
    </BrokerNotice>
    <BrokerNotice>
      <BrokerNo>华泰期货_CTP主席</BrokerNo>
      <NoticeList>
        <Notice>
          <NoticeDate>20260901</NoticeDate>
          <Content>&lt;p&gt;尊敬的投资者：&amp;nbsp; &lt;/p&gt;&lt;p&gt;一、关于调整集运指数（欧线）期货新上市合约交易限额的通知。&lt;/p&gt;&lt;p&gt;特此公告&lt;/p&gt;</Content>
        </Notice>
        <Notice>
          <NoticeDate>20260301</NoticeDate>
          <Content>&lt;p&gt;旧公告不采&lt;/p&gt;</Content>
        </Notice>
      </NoticeList>
    </BrokerNotice>
  </BrokerNoticeList>
</NoticeInfo>
"""


def test_parse_notice_xml_structure():
    out = T.parse_notice_xml(SAMPLE_XML)
    assert len(out["last_login"]) == 2
    assert out["last_login"][0][0] == "20260807"
    assert len(out["notices"]) == 2
    n = out["notices"][0]
    assert n["broker"] == "华泰期货_CTP主席"
    assert n["date"] == "20260901"
    assert "欧线" in n["content"]
    assert "<p>" not in n["content"]          # HTML 已去标签
    assert "&amp;nbsp;" not in n["content"]   # 实体已反转义


def test_recent_notices_filter():
    out = T.parse_notice_xml(SAMPLE_XML)
    items = T.recent_notices(out, days=7, now=datetime(2026, 9, 6))
    assert len(items) == 1
    assert items[0]["date"] == "20260901"


def test_recent_notices_max_per_day():
    xml = SAMPLE_XML.replace("20260901", "20260903")
    out = T.parse_notice_xml(xml + xml.replace("20260903", "20260905"))
    items = T.recent_notices(out, days=7, now=datetime(2026, 9, 6), max_per_day=1)
    dates = [it["date"] for it in items]
    assert len(dates) == len(set(dates))      # 同一天最多 1 条
    assert "20260905" in dates


def test_notices_to_news_fields():
    out = T.parse_notice_xml(SAMPLE_XML)
    items = T.notices_to_news(T.recent_notices(out, days=7, now=datetime(2026, 9, 6)))
    assert len(items) == 1
    assert items[0]["source"] == "ths_notice"
    assert items[0]["time"] == "2026-09-01 09:00:00"
    assert items[0]["important"] == 1
    assert "[华泰期货_CTP主席公告]" in items[0]["content"]


def test_read_notice_file_missing():
    assert T.read_notice_file(r"C:\no_such_file.xml") is None


def test_parse_quote_tsv():
    cols = ["名称", "合约代码", "最新价", "涨跌幅", "成交量", "持仓量", "买价", "卖价"]
    row = ["螺纹钢", "rb2610", "3756", "+0.8%", "234567", "890123", "3755", "3757"]
    out = T.parse_quote_tsv(cols, row)
    assert out["price"] == "3756"
    assert out["code"] == "rb2610"
    assert out["bid"] == "3755"
    assert out["ask"] == "3757"
    assert out["source"] == "ths_ui"


def test_parse_quote_tsv_unknown_columns():
    out = T.parse_quote_tsv(["x", "y"], ["a", "b"])
    assert out is None

# ---------------------------------------------------------------- 第十六轮新增：OCR 行过滤/解析

class TestIsQuoteLike:
    def test_real_quote_row(self):
        row = "螺纹钢\tRB2701\t3,420.00\t+12\t+0.35%\t120,000\t300,000"
        assert T.is_quote_like(row) is True

    def test_ui_chrome_row(self):
        assert T.is_quote_like("自选\t合约\t期货\t期权\t套利") is False

    def test_macd_row(self):
        assert T.is_quote_like("MACD\t0.00\t0.00") is False

    def test_statusbar_row(self):
        assert T.is_quote_like("沪指 3940.55 +7.85 +0.20% 9155.66亿\t同花顺商品") is False

    def test_too_few_cells(self):
        assert T.is_quote_like("名称") is False

    def test_no_numbers(self):
        assert T.is_quote_like("豆粕\tM2701\t上涨\t下跌") is False


class TestParseQuoteOcrRow:
    def test_typical_row(self):
        row = ["螺纹钢", "RB2701", "3,420.00", "+12", "+0.35%", "120,000", "300,000"]
        q = T.parse_quote_ocr_row(row)
        assert q is not None
        assert q["variety"] == "螺纹钢"
        assert q["code"] == "RB2701"
        assert q["price"] == "3,420.00"

    def test_row_without_code(self):
        row = ["豆粕", "2,800", "-10", "-0.36%", "50,000"]
        q = T.parse_quote_ocr_row(row)
        assert q is not None
        assert q["variety"] == "豆粕"
        assert q["price"] == "2,800"

    def test_garbage_row(self):
        assert T.parse_quote_ocr_row(["自选", "合约", "期货"]) is None

    def test_empty_row(self):
        assert T.parse_quote_ocr_row([]) is None

    def test_single_num(self):
        row = ["白糖", "SR2701", "5,800"]
        q = T.parse_quote_ocr_row(row)
        assert q is not None
        assert q["price"] == "5,800"

    def test_source_tag(self):
        q = T.parse_quote_ocr_row(["铜", "CU2701", "68,000", "+200"])
        assert q["source"] == "ths_ocr"

    def test_variety_tail_cleanup(self):
        q = T.parse_quote_ocr_row(["氧化铝2610色", "ao2610", "2737", "-0.3"])
        assert q["variety"] == "氧化铝2610"
        assert q["code"] == "AO2610"

    def test_variety_tail_cleanup_dong(self):
        q = T.parse_quote_ocr_row(["豆粕2701动", "m2701", "3415", "+0.3"])
        assert q["variety"] == "豆粕2701"

    def test_real_ocr_lines_parsed(self):
        lines = [
            "jm2701\t焦煤2701\t1689.5\t+2.7",
            "烧碱2611\t1968\t+0.7\t1661.5\t1.03%\t2\tSH2611",
            "3\tm2701\t豆粕2701\t3415\t+0.3\t1644.5\t0.00%",
            "5\tao2610\t氧化铝2610色\t2737\t-0.3",
        ]
        parsed = [T.parse_quote_ocr_row(l.split("\t")) for l in lines]
        assert all(p is not None for p in parsed)
        assert parsed[0]["code"] == "JM2701"
        assert parsed[1]["price"] == "1968"
        assert parsed[2]["chg_pct"] == "+0.3"
        assert parsed[3]["variety"] == "氧化铝2610"

    def test_noise_rows_rejected(self):
        noise = [
            "共有0只代码\t1695.5\t3.10%\t期货通自选▼",
            "序号\t代码\t名称\t现价\t1678.5\t2.07%",
            "现价\t1750.0\t代码\t名称\t涨幅",
        ]
        for l in noise:
            assert T.is_quote_like(l) is False, l
