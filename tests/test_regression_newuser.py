"""回归测试：新用户实测中发现的问题。

每个用例对应一个真实踩过的坑，防止修复后被改回去。
"""

import pytest

from tznovel.fetch.base import FetchError, classify
from tznovel.report.precheck import check_intro


class TestFetchShortPageNotBlocked:
    """实测：example.com 只有 171 字，曾被误判成 IP_BLOCKED。

    新用户第一次跑 fetch 就看到"IP_BLOCKED（被封了）"会以为自己的网络有问题，
    实际只是那个页面内容本来就短。
    """

    def test_short_page_without_block_markers(self):
        err, reason = classify(200, "<html><body>Hello. This is a short page.</body></html>")
        assert err == FetchError.EMPTY_SITE
        assert "过短" in reason
        # 关键：不能说成"被封"
        assert err != FetchError.IP_BLOCKED

    def test_short_page_with_block_marker_still_blocked(self):
        """带拦截特征的短页面，仍应判 IP_BLOCKED。"""
        err, _ = classify(200, "<title>Just a moment...</title>")
        assert err == FetchError.IP_BLOCKED

    def test_403_still_blocked(self):
        err, _ = classify(403, "403 Forbidden")
        assert err == FetchError.IP_BLOCKED


class TestIntroMultiline:
    """实测：多行简介曾被只取第一行，字数严重少算。

    原实现用 `(.+?)\\n` 只抓一行，导致：
      · 三行简介只算第一行 → 字数少报
      · 自标字数在最后一行 → 抓不到
    """

    def test_multiline_intro_counted_fully(self):
        """三行简介应被合并统计，而不是只取第一行。"""
        line1 = "第一行的内容。"
        line2 = "第二行的内容。"
        line3 = "第三行的内容。"
        md = f"""# 报告

## 2. 内容简介
{line1}
{line2}
{line3}
（{len(line1 + line2 + line3)} 字）

## 其他
"""
        item = check_intro(md)
        # 自标字数与三行合计一致 → 说明三行都被算进去了
        assert item.status == "PASS", f"多行简介未被正确合并：{item.detail}"
        expected = len(line1 + line2 + line3)
        assert any(str(expected) in d for d in item.detail), \
            f"应统计出 {expected} 字：{item.detail}"

    def test_declared_count_detected(self):
        md = """## 2. 内容简介
主角是个普通人。（8 字）

## 其他
"""
        item = check_intro(md)
        # 自标 8，实际「主角是个普通人。」= 8 字
        assert "8" in str(item.detail)

    def test_declared_mismatch_flagged(self):
        md = """## 2. 内容简介
主角是个普通人，他日子过得平淡，直到某天捡到一件古物。（99 字）

## 其他
"""
        item = check_intro(md)
        assert item.status == "FAIL", f"自标 99 实际 27，应报 FAIL：{item.detail}"

    def test_correct_declaration_passes(self):
        body = "主角是个普通人。"
        md = f"""## 2. 内容简介
{body}（{len(body)} 字）

## 其他
"""
        item = check_intro(md)
        assert item.status == "PASS", f"应 PASS：{item.detail}"

    def test_over_length_fails(self):
        long_intro = "很长" * 70
        md = f"""## 2. 内容简介
{long_intro}

## 其他
"""
        item = check_intro(md)
        assert item.status == "FAIL"
        assert "120" in item.message


class TestTxtInputSupported:
    """实测：纯 txt 文件能分析，但 README 此前没写这个用法。"""

    def test_txt_body_analyzable(self):
        from tznovel.analyze.person import detect_person
        from tznovel.analyze.stats import analyze_text

        txt = "他走进了房间。他看着窗外的雪。他坐下来，点了一支烟。" * 10
        chapters = [{"label": "1", "title": "txt", "body": txt}]
        assert analyze_text(chapters).total_chars > 0
        assert detect_person(chapters).narr_sents > 0
