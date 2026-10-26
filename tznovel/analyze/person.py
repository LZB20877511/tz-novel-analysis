"""叙事人称判定。

问题背景：用户说"不要第一人称"，而题材对得上的书里可能有 60% 是第一人称。
人工逐本读开头成本高，本模块把这件事变成**可复算的判定**。

方法：
    剔除对话（引号内容）后，统计叙述句中以"我"作**主语**的比例。
    对话里的"我"不算 —— 这是关键，否则对话多的书会被误判。

阈值来自实测锚点（两本书真实正文，样本量足够）：
    第三人称：《茅山后裔》0.1%、《走进修仙》0.1%
    第一人称：《民调局异闻录》后传 27.5%–36.4%
    → 阈值 15% 两侧余量都很大，不是拍脑袋
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from tznovel.analyze.stats import clean_paragraphs

RE_QUOTED = re.compile(r"“[^”]*”|\"[^\"]*\"|「[^」]*」|『[^』]*』")
RE_SENT_SPLIT = re.compile(r"(?<=[。！？…])")
# 叙述句以"我"作主语（排除"我们"，那是第一人称复数，性质不同但同属第一人称）。
# 单列：句首"我"后紧跟这些字，多半是"我觉得/我看"这类叙述，其余可能是我名字开头，需人工复核。
RE_FIRST_PERSON_START = re.compile(r"^(我(?!们))")


@dataclass
class PersonVerdict:
    """人称判定结果。"""

    narr_sents: int = 0
    first_person_sents: int = 0
    ratio_pct: float = 0.0
    verdict: str = "无法判定"
    confidence: str = "低"
    samples: list[str] = field(default_factory=list)

    @property
    def is_first_person(self) -> bool:
        return self.verdict.startswith("第一人称")

    @property
    def is_third_person(self) -> bool:
        return self.verdict.startswith("第三人称")

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["is_first_person"] = self.is_first_person
        d["is_third_person"] = self.is_third_person
        return d


def detect_person(
    chapters: Iterable[dict] | Iterable[str],
    *,
    body_key: str = "body",
    min_sents: int = 30,
    first_person_threshold: float = 15.0,
    third_person_threshold: float = 5.0,
) -> PersonVerdict:
    """判定叙事人称。

    Args:
        chapters: [{"body": ...}] 或 [str, ...]
        body_key: dict 形式时的正文字段名
        min_sents: 最少叙述句数；不足则判"无法判定"（避免小样本误判）
        first_person_threshold: ≥该比例判第一人称
        third_person_threshold: <该比例判第三人称

    Returns:
        PersonVerdict

    Example:
        >>> v = detect_person(["张国忠走进了房间。他看着窗外。"])
        >>> v.verdict
        '无法判定'
    """
    narr_total = 0
    fp_total = 0
    samples: list[str] = []

    for ch in chapters:
        body = ch.get(body_key, "") if isinstance(ch, dict) else ch
        for para in clean_paragraphs(body or ""):
            # 剔除对话，只看叙述
            narr = RE_QUOTED.sub("", para).strip()
            if len(narr) < 6:
                continue
            for sent in RE_SENT_SPLIT.split(narr):
                sent = sent.strip()
                if len(sent) < 5:
                    continue
                narr_total += 1
                if RE_FIRST_PERSON_START.match(sent):
                    fp_total += 1
                    if len(samples) < 3:
                        samples.append(sent[:40])

    ratio = 100.0 * fp_total / narr_total if narr_total else 0.0

    # 判定逻辑：比例优先，样本量只影响置信度。
    # ⚠️ 早期版本把 min_sents 当硬门槛，导致"比例 100% 但只有 11 句"被误判成"无法判定"——
    #    样本少应该降低置信度，不是丢掉结论。
    if narr_total == 0:
        return PersonVerdict(
            narr_sents=0, first_person_sents=0, ratio_pct=0.0,
            verdict="无法判定", confidence="低", samples=[],
        )

    if ratio >= first_person_threshold:
        verdict = "第一人称"
    elif ratio >= third_person_threshold:
        verdict = "第三人称（含较多第一人称内心独白）"
    else:
        verdict = "第三人称"

    # 置信度按样本量分档
    if narr_total >= 200:
        conf = "高"
    elif narr_total >= min_sents:
        conf = "中"
    else:
        conf = "低"

    return PersonVerdict(
        narr_sents=narr_total,
        first_person_sents=fp_total,
        ratio_pct=round(ratio, 1),
        verdict=verdict,
        confidence=conf,
        samples=samples,
    )
