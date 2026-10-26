"""抓取层测试：错误分类 / 编码解码 / 正文提取。

这些测试的判据来自实测踩过的坑，不是想当然。
"""

import pytest

from tznovel.fetch.base import (
    FetchError,
    classify,
    decode_bytes,
    inspect_text,
)
from tznovel.fetch.extract import extract_body


class TestClassify:
    def test_dead_page(self):
        err, _ = classify(404, "<html>not found</html>")
        assert err == FetchError.FATAL

    def test_empty_site_marker(self):
        """站点自身无内容 —— 这是最容易被误判为"反爬"的一类。"""
        err, reason = classify(200, "<div>转码失败！请换源</div>")
        assert err == FetchError.EMPTY_SITE
        assert "站点自身无内容" in reason

    def test_blocked_by_403(self):
        err, _ = classify(403, "403 Forbidden nginx")
        assert err == FetchError.IP_BLOCKED

    def test_blocked_by_marker(self):
        err, _ = classify(200, "<title>Just a moment...</title>" + "x" * 1000)
        assert err == FetchError.IP_BLOCKED

    def test_rate_limit(self):
        err, _ = classify(429, "too many requests")
        assert err == FetchError.RATE_LIMIT

    def test_retryable_5xx(self):
        err, _ = classify(502, "bad gateway")
        assert err == FetchError.RETRYABLE

    def test_short_content_is_suspicious(self):
        """短页面应判 EMPTY_SITE，不是 IP_BLOCKED。

        实测教训：example.com 只有 171 字，曾被误报成"被封"，
        用户会以为自己的网络出了问题。
        """
        err, reason = classify(200, "<html>" + "短" * 50 + "</html>")
        assert err == FetchError.EMPTY_SITE
        assert "过短" in reason

    def test_normal_page(self):
        html = "<html><body>" + "正常正文内容。" * 200 + "</body></html>"
        err, reason = classify(200, html)
        assert err is None
        assert "正文" in reason


class TestDecodeBytes:
    def test_utf8(self):
        raw = "这是中文正文".encode("utf-8")
        text, enc, _ = decode_bytes(raw)
        assert text == "这是中文正文"
        assert enc == "utf-8"

    def test_gbk_fallback(self):
        """GBK 编码的页面必须能正确解码，否则整章变乱码。"""
        raw = "这是GBK编码的中文".encode("gb18030")
        text, enc, _ = decode_bytes(raw)
        assert "GBK" in text
        assert enc in ("gb18030", "utf-8")

    def test_never_returns_garbage_silently(self):
        """解码结果必须保留诊断信息，便于判断是否可用。"""
        raw = b"\xff\xfe broken bytes \xff"
        text, enc, memo = decode_bytes(raw)
        assert isinstance(memo, dict)
        assert "utf8_ufffd" in memo


class TestInspectText:
    def test_clean_text_usable(self):
        r = inspect_text("这是干净的正文内容，没有任何问题。")
        assert r["usable"] is True
        assert r["pua"] == 0
        assert r["ufffd"] == 0

    def test_pua_detected(self):
        r = inspect_text("正文\ue000\ue001内容")
        assert r["pua"] == 2
        assert r["usable"] is False

    def test_garbled_head_not_usable(self):
        """首行乱码 → 判不可用。这是 pua=0 时唯一能抓住编码错乱的判据。"""
        r = inspect_text("锟斤拷锟斤拷" + "正文" * 100)
        assert r["head_readable"] is False
        assert r["usable"] is False

    def test_low_pua_but_bad_head(self):
        """关键场景：pua 低但首行乱码 —— 旧阈值会误判为可用。"""
        r = inspect_text("\ufffd\ufffd\ufffd这里乱码了" + "正常内容" * 50)
        assert r["pua"] == 0          # pua 查不出
        assert r["usable"] is False   # 但必须判不可用


class TestExtractBody:
    def test_extract_from_content_div(self):
        html = '<html><body><div id="content">' + "正文内容。" * 100 + "</div></body></html>"
        r = extract_body(html)
        assert r.ok
        assert "正文内容" in r.body

    def test_strip_ads(self):
        """部分站点把广告塞在正文 div 里，必须剥离。"""
        html = ('<div id="content"><div id="center_tip">广告广告</div>'
                + "真正的正文。" * 100 + "</div>")
        r = extract_body(html)
        assert "广告广告" not in r.body
        assert r.stripped_ads > 0

    def test_strip_navigation_junk(self):
        html = '<div id="content">上一章\n' + "正文内容。" * 100 + "\n下一章\n返回目录</div>"
        r = extract_body(html)
        assert "上一章" not in r.body
        assert "返回目录" not in r.body

    def test_br_to_newline(self):
        """<br> 必须转成换行，段落要能分开（用够长的段落，避免被噪声过滤）。"""
        html = ('<div id="content">第一段的内容比较长一些<br/>'
                '第二段的内容同样也够长<br/>' + "填充内容。" * 100 + "</div>")
        r = extract_body(html)
        assert "\n" in r.body
        assert "第一段的内容比较长一些" in r.body
        assert "第二段的内容同样也够长" in r.body

    def test_fallback_when_no_container(self):
        """没有标准容器时用文本密度兜底，不能直接返回空。"""
        html = "<html><body><p>" + "这是一段比较长的正文内容，" * 100 + "</p></body></html>"
        r = extract_body(html)
        assert r.chars > 300
        assert "fallback" in r.matched_pattern

    def test_too_short_fails(self):
        r = extract_body("<div id='content'>短</div>")
        assert r.ok is False
