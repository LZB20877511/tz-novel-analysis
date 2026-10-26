"""文风量化模块测试。"""

import pytest

from tznovel.analyze.stats import (
    analyze_text,
    clean_paragraphs,
)


class TestCleanParagraphs:
    def test_removes_empty_lines(self):
        assert clean_paragraphs("第一行\n\n\n第二行") == ["第一行", "第二行"]

    def test_removes_leading_title(self):
        body = "第一章 开始\n这是正文内容。"
        assert clean_paragraphs(body)[0] == "这是正文内容。"

    def test_removes_update_mark(self):
        body = "正文在这里（第一更）继续。"
        assert "第一更" not in clean_paragraphs(body)[0]

    def test_removes_optail(self):
        body = "正文内容。\n请记住本站域名"
        assert all("请记住本站" not in p for p in clean_paragraphs(body))

    def test_keeps_short_dialogue(self):
        """短对白不能被当噪声删掉（网文常态）。"""
        paras = clean_paragraphs("“走。”\n“好。”")
        assert len(paras) == 2


class TestAnalyzeText:
    def test_basic_metrics(self):
        chapters = [{"label": 1, "title": "第一章", "body": "他走了。她笑了。天亮了。"}]
        r = analyze_text(chapters)
        assert r.total_chars == 12
        assert r.chapters[0].sents == 3

    def test_dialogue_detection(self):
        chapters = [{"body": "“你好。”他说。\n“再见。”"}]
        r = analyze_text(chapters)
        assert r.dlg_char_pct > 0

    def test_pua_detection(self):
        chapters = [{"body": "正文\ue000\ue001内容"}]
        r = analyze_text(chapters)
        assert r.pua == 2

    def test_latin_detection(self):
        chapters = [{"body": "他的脸sè变了"}]
        r = analyze_text(chapters)
        assert r.latin == 1

    def test_cheap_words_split(self):
        """A/B 两组必须分开统计 —— 只报 A 组会给人"毫无模板感"的错觉。"""
        chapters = [{"body": "忽然他来了。竟然是她。顿时安静。"}]
        r = analyze_text(chapters)
        assert r.cheap_a_total == 2  # 忽然 + 顿时
        assert r.cheap_b_total == 1  # 竟然

    def test_question_beats_exclaim(self):
        chapters = [{"body": "为什么？怎么会？这到底是什么？"}]
        r = analyze_text(chapters)
        assert r.question_beats_exclaim is True

    def test_empty_input(self):
        r = analyze_text([])
        assert r.total_chars == 0
        assert r.chapters == []

    def test_weighted_average_across_chapters(self):
        """长短章混合时要用加权平均，不能简单平均。"""
        chapters = [
            {"body": "短句。" * 5},
            {"body": "这是一个非常长的句子，包含了很多很多的内容，" * 20},
        ]
        r = analyze_text(chapters)
        assert r.avg_sent > 0
        assert r.total_chars > 0

    def test_tuple_input(self):
        r = analyze_text([("第一章", "他走了。")])
        assert r.total_chars == 4
        assert r.chapters[0].label == "第一章"

    def test_to_dict_serializable(self):
        import json
        r = analyze_text([{"body": "正文内容。"}])
        json.dumps(r.to_dict(), ensure_ascii=False)  # 不抛异常即可
