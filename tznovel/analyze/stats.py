"""文风量化分析。

把"文笔好不好"这种主观印象，拆成可数指标：
句长分布、段落长度、对话占比、标点密度、手法词频。

⚠️ 设计原则：**只报数，不下判断**。
指标交给评审者（人或模型）去解释，本模块不输出"文笔分"。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

# ---------- 词表 ----------

# 手法/转折信号词：作者用来推进节奏的副词
SIGNAL_WORDS: tuple[str, ...] = (
    "忽然", "猛地", "猛然", "瞬间", "陡然", "顿时", "不由", "忍不住",
    "竟然", "赫然", "依旧", "依然", "仿佛", "似乎", "缓缓", "渐渐", "慢慢",
    "霎那", "刹那", "旋即", "突然", "忽而", "骤然",
)

# 说话动词：判断人物声音是否同质化
SPEECH_VERBS: tuple[str, ...] = (
    "说道", "道：", "问道", "笑道", "喝道", "沉声道", "低声道", "淡淡道",
    "淡然道", "微笑道", "叫道", "狂吼", "怒吼", "喃喃", "冷声道",
)

# 廉价转折词分两组报数（见 docs/口径说明）：
#   A 组：真正的模板化信号，命中越少越好
#   B 组：常被误认为"有文采"，但堆多了同样是惰性
CHEAP_A: tuple[str, ...] = ("忽然", "顿时", "陡然", "骤然", "渐渐", "简直", "猛地")
CHEAP_B: tuple[str, ...] = ("竟然", "居然", "不由", "忍不住", "淡淡", "猛然", "霎那", "刹那")

RE_SENT_SPLIT = re.compile(r"(?<=[。！？…])")
RE_QUOTED = re.compile(r"“[^”]*”|\"[^\"]*\"|「[^」]*」")
RE_PUA = re.compile(r"[\uE000-\uF8FF]")
RE_LATIN = re.compile(r"[A-Za-z\u00C0-\u024F]+")
RE_LEADING_TITLE = re.compile(r"^\s*(\d{1,4}[、.．]|第[零一二三四五六七八九十百千两0-9]+[章回节])")
RE_OPTAIL = re.compile(
    r"^(还有[，,].{0,20}建议.{0,10}看.{0,6}|\(https?:?\)|（https?:?）|"
    r"更多到[，,]?\s*地址.{0,20}|请记住本站.{0,20})\s*$"
)
RE_UPDATE_MARK = re.compile(r"[（(]\s*第[一二三四五六七八九十0-9]+\s*更\s*[)）]")


@dataclass
class ChapterStats:
    """单章统计结果。"""

    label: str = ""
    title: str = ""
    chars: int = 0
    paras: int = 0
    sents: int = 0
    avg_sent: float = 0.0
    avg_para: float = 0.0
    max_sent: int = 0
    dlg_sent_pct: float = 0.0
    dlg_char_pct: float = 0.0
    excl_per_k: float = 0.0
    quest_per_k: float = 0.0
    ellipsis_per_k: float = 0.0
    long60_pct: float = 0.0
    short15_pct: float = 0.0
    pua: int = 0
    latin: int = 0


@dataclass
class StatsResult:
    """整批章节的汇总结果。"""

    chapters: list[ChapterStats] = field(default_factory=list)
    total_chars: int = 0
    total_paras: int = 0
    total_sents: int = 0
    avg_sent: float = 0.0
    avg_para: float = 0.0
    dlg_sent_pct: float = 0.0
    dlg_char_pct: float = 0.0
    excl_per_k: float = 0.0
    quest_per_k: float = 0.0
    ellipsis_per_k: float = 0.0
    long60_pct: float = 0.0
    short15_pct: float = 0.0
    pua: int = 0
    latin: int = 0
    latin_per_k: float = 0.0
    signal_words: dict[str, int] = field(default_factory=dict)
    speech_verbs: dict[str, int] = field(default_factory=dict)
    cheap_a: dict[str, int] = field(default_factory=dict)
    cheap_b: dict[str, int] = field(default_factory=dict)

    @property
    def cheap_a_total(self) -> int:
        return sum(self.cheap_a.values())

    @property
    def cheap_b_total(self) -> int:
        return sum(self.cheap_b.values())

    @property
    def question_beats_exclaim(self) -> bool:
        """问号 > 感叹号 —— 少见的叙述指纹（常见于反问式幽默/克制叙述）。"""
        return self.quest_per_k > self.excl_per_k

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["chapters"] = [c.__dict__ for c in self.chapters]
        d["cheap_a_total"] = self.cheap_a_total
        d["cheap_b_total"] = self.cheap_b_total
        d["question_beats_exclaim"] = self.question_beats_exclaim
        return d


def clean_paragraphs(body: str, strip_title: bool = True) -> list[str]:
    """清洗正文段落。

    去空行、章末运营句、更新序号标记，以及与标题重复的首行。
    """
    paras = [p.strip() for p in body.replace("\r\n", "\n").split("\n") if p.strip()]
    if strip_title and paras and RE_LEADING_TITLE.match(paras[0]) and len(paras[0]) < 40:
        paras = paras[1:]
    out = []
    for p in paras:
        if RE_OPTAIL.match(p):
            continue
        p = RE_UPDATE_MARK.sub("", p).strip()
        if p:
            out.append(p)
    return out


def _chapter_stats(body: str, label: str = "", title: str = "") -> ChapterStats | None:
    paras = clean_paragraphs(body)
    if not paras:
        return None
    text = "".join(paras)
    n = len(text)
    if n == 0:
        return None

    sents = [s for s in RE_SENT_SPLIT.split(text) if s.strip()]
    ns = len(sents) or 1
    quoted = "".join(RE_QUOTED.findall(text))
    dlg_sents = sum(1 for s in sents if "“" in s or "”" in s or "「" in s)

    return ChapterStats(
        label=label,
        title=title,
        chars=n,
        paras=len(paras),
        sents=len(sents),
        avg_sent=round(sum(len(s) for s in sents) / ns, 1),
        avg_para=round(n / len(paras), 1),
        max_sent=max((len(s) for s in sents), default=0),
        dlg_sent_pct=round(100 * dlg_sents / ns, 1),
        dlg_char_pct=round(100 * len(quoted) / n, 1),
        excl_per_k=round(1000 * text.count("！") / n, 2),
        quest_per_k=round(1000 * text.count("？") / n, 2),
        ellipsis_per_k=round(1000 * text.count("…") / n, 2),
        long60_pct=round(100 * sum(1 for s in sents if len(s) >= 60) / ns, 1),
        short15_pct=round(100 * sum(1 for s in sents if len(s) <= 15) / ns, 1),
        pua=len(RE_PUA.findall(text)),
        latin=len(RE_LATIN.findall(text)),
    )


def _wavg(values: Sequence[float], weights: Sequence[float]) -> float:
    tw = sum(weights)
    return round(sum(v * w for v, w in zip(values, weights)) / tw, 1) if tw else 0.0


def analyze_text(
    chapters: Iterable[dict] | Iterable[tuple[str, str]],
    *,
    label_key: str = "label",
    title_key: str = "title",
    body_key: str = "body",
) -> StatsResult:
    """分析一批章节。

    Args:
        chapters: 可以是 [{"label":..,"title":..,"body":..}] 或 [(label, body)] 形式
        label_key / title_key / body_key: dict 形式时的字段名

    Returns:
        StatsResult

    Example:
        >>> r = analyze_text([{"label": 1, "title": "第一章", "body": "他走了。她笑了。"}])
        >>> r.total_chars
        9
    """
    per: list[ChapterStats] = []
    texts: list[str] = []

    for i, ch in enumerate(chapters):
        if isinstance(ch, dict):
            label = str(ch.get(label_key, i + 1))
            title = str(ch.get(title_key, ""))
            body = ch.get(body_key, "") or ""
        else:
            label, body = str(ch[0]), ch[1]
            title = ""
        st = _chapter_stats(body, label, title)
        if st:
            per.append(st)
            texts.append("".join(clean_paragraphs(body)))

    if not per:
        return StatsResult()

    total = sum(c.chars for c in per)
    n_para = sum(c.paras for c in per)
    n_sent = sum(c.sents for c in per)
    all_text = "".join(texts)

    def wc(words: Iterable[str]) -> dict[str, int]:
        c: Counter[str] = Counter()
        for w in words:
            c[w] = all_text.count(w)
        return {k: v for k, v in c.most_common() if v}

    return StatsResult(
        chapters=per,
        total_chars=total,
        total_paras=n_para,
        total_sents=n_sent,
        avg_sent=_wavg([c.avg_sent for c in per], [c.sents for c in per]),
        avg_para=round(total / n_para, 1) if n_para else 0.0,
        dlg_sent_pct=_wavg([c.dlg_sent_pct for c in per], [c.sents for c in per]),
        dlg_char_pct=_wavg([c.dlg_char_pct for c in per], [c.chars for c in per]),
        excl_per_k=_wavg([c.excl_per_k for c in per], [c.chars for c in per]),
        quest_per_k=_wavg([c.quest_per_k for c in per], [c.chars for c in per]),
        ellipsis_per_k=_wavg([c.ellipsis_per_k for c in per], [c.chars for c in per]),
        long60_pct=_wavg([c.long60_pct for c in per], [c.sents for c in per]),
        short15_pct=_wavg([c.short15_pct for c in per], [c.sents for c in per]),
        pua=sum(c.pua for c in per),
        latin=sum(c.latin for c in per),
        latin_per_k=round(1000 * sum(c.latin for c in per) / total, 2) if total else 0.0,
        signal_words=wc(SIGNAL_WORDS),
        speech_verbs=wc(SPEECH_VERBS),
        cheap_a=wc(CHEAP_A),
        cheap_b=wc(CHEAP_B),
    )
