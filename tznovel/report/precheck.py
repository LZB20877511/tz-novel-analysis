"""报告送审前自检。

为什么需要这个：实测发现，**有三类错误每次都会发生，且都程序能查**：

    1. 简介字数 —— 手工估了 4 次，4 次全错，且全部少报
    2. 同一处剧透写两遍 —— 连续 3 份报告被审校抓出
    3. 加权总分算错 —— 曾出现 5.90 vs 实际 5.85

这些错误零技术含量，不该占用人工审校的注意力。本模块把它们机器化。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------- 剧透模式（A0 闸门） ----------
SPOILER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"最后.{0,6}(死|牺牲|成神|在一起|结婚)", "结局"),
    (r"其实.{0,8}(是|就是).{0,10}(反派|凶手|卧底|分身)", "身份反转"),
    (r"凶手是", "凶手"),
    (r"(真相是|原来).{0,12}(都是|并非)", "关键揭密"),
    (r"最终.{0,6}(死|活|败|胜)", "结局"),
)

# ---------- 不实陈述（时态） ----------
FALSE_CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"已(通过|过)\s*spoiler-guard", "草稿不应声称「已过闸门」，应为「已提交」"),
    (r"已(通过|过)\s*(闸门|审校)", "同上"),
)

# ---------- 必备结构 ----------
REQUIRED_SECTIONS: tuple[tuple[str, str], ...] = (
    (r"一句话结论|##\s*0\.", "结论先行"),
    (r"内容简介", "内容简介"),
    (r"覆盖度", "取证覆盖度"),
    (r"依据[:：]", "证据标签"),
)

WEIGHTS: dict[str, float] = {"W": 0.25, "C": 0.20, "T": 0.15, "E": 0.15, "P": 0.15, "X": 0.10}


@dataclass
class CheckItem:
    """单项检查结果。"""

    code: str
    name: str
    status: str  # PASS / WARN / FAIL / SKIP
    message: str
    detail: list[str] = field(default_factory=list)


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def check_intro(text: str) -> CheckItem:
    """简介字数：≤120 且自标值 = 实际值。"""
    m = re.search(r"(?s)##\s*2[\.、].{0,14}简介.{0,24}\n+(.+?)\n", text)
    if not m:
        return CheckItem("C1", "简介字数", "SKIP", "未找到 §2 简介段")
    intro = re.sub(r"[*_`>]", "", m.group(1).strip()).strip()
    n_plain = len(intro)

    tail = text[m.end(): m.end() + 160]
    dm = re.search(r"[（(]\s*(\d+)\s*字[^）)]*[）)]", m.group(1) + tail)
    declared = int(dm.group(1)) if dm else None

    detail = [f"实际（含标点）{n_plain} 字", f"草稿自标 {declared if declared is not None else '未标'}"]

    if n_plain > 120:
        return CheckItem("C1", "简介字数", "FAIL", f"{n_plain} 字 > 120 上限", detail)
    if declared is not None and declared != n_plain:
        return CheckItem(
            "C1", "简介字数", "FAIL",
            f"自标 {declared} 实际 {n_plain}（差 {abs(declared - n_plain)}）——实测 4/4 份报告都在此出错",
            detail,
        )
    return CheckItem("C1", "简介字数", "PASS", f"{n_plain}/120", detail)


def check_spoiler(text: str, extra_words: tuple[str, ...] = ()) -> CheckItem:
    """A0 剧透正则 + 自定义敏感词。"""
    hits: list[str] = []
    for pat, label in SPOILER_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append(f"L{_line_of(text, m.start())} [{label}] {m.group(0)}")
    for w in extra_words:
        for m in re.finditer(re.escape(w), text):
            hits.append(f"L{_line_of(text, m.start())} [敏感词] {w}")
    if hits:
        return CheckItem("C2", "剧透扫描", "WARN", f"命中 {len(hits)} 处，需逐条裁定（命中≠越线）", hits)
    return CheckItem("C2", "剧透扫描", "PASS", "A0 正则 + 敏感词 全 0 命中")


def check_duplicate(text: str, sensitive: tuple[str, ...] = (), min_len: int = 14) -> CheckItem:
    """同句重复扫描 —— 实测连续 3 份报告栽在这里。"""
    sents = [s.strip() for s in re.split(r"[。！？\n]+", text) if s.strip()]
    seen: dict[str, list[str]] = {}
    for s in sents:
        key = re.sub(r"[，、；：\"“”「」（）()\s*_`>|#\-\u3000]", "", s)
        if len(key) >= min_len:
            seen.setdefault(key, []).append(s)

    dups: list[str] = []
    for key, occ in seen.items():
        if len(occ) < 2:
            continue
        if len(key) >= 18 or any(w in key for w in sensitive):
            dups.append(f"出现 {len(occ)} 次：{occ[0][:40]}")

    if dups:
        return CheckItem("C3", "同句重复", "WARN", f"{len(dups)} 处危险表述重复（必须同改）", dups)
    return CheckItem("C3", "同句重复", "PASS", "未发现重复的危险表述")


def check_weights(text: str, supplied: dict[str, float] | None = None) -> CheckItem:
    """六维加权核算。"""
    vals = dict(supplied or {})
    if len(vals) < 6:
        for key, pat in (
            ("W", r"文[笔风][^|\n]*\|\s*0\.25\s*\|\s*\**([\d.]+)"),
            ("C", r"人物[^|\n]*\|\s*0\.20\s*\|\s*\**([\d.]+)"),
            ("T", r"事物[^|\n]*\|\s*0\.15\s*\|\s*\**([\d.]+)"),
            ("E", r"情感[^|\n]*\|\s*0\.15\s*\|\s*\**([\d.]+)"),
            ("P", r"情节[^|\n]*\|\s*0\.15\s*\|\s*\**([\d.]+)"),
            ("X", r"体验[^|\n]*\|\s*0\.10\s*\|\s*\**([\d.]+)"),
        ):
            m = re.search(pat, text)
            if m:
                try:
                    vals[key] = float(m.group(1))
                except ValueError:
                    pass

    if len(vals) < 6:
        return CheckItem("C4", "加权核算", "SKIP", f"仅识别 {len(vals)}/6 维度，跳过")

    total = sum(WEIGHTS[k] * vals[k] for k in WEIGHTS)
    claimed = re.findall(r"总分[^|\n]*\*\*([\d.]+)\*\*", text)
    bad = [c for c in claimed if abs(float(c) - total) > 0.06]

    detail = [f"各维 {vals}", f"精确值 {round(total, 4)}"]
    if bad:
        return CheckItem("C4", "加权核算", "FAIL", f"文中总分 {bad} ≠ 核算 {round(total, 2)}", detail)
    return CheckItem("C4", "加权核算", "PASS", f"= {round(total, 4)}", detail)


def check_sections(text: str) -> CheckItem:
    """必备结构。"""
    missing = [name for pat, name in REQUIRED_SECTIONS if not re.search(pat, text)]
    if missing:
        return CheckItem("C5", "必备结构", "FAIL", f"缺：{missing}", missing)
    return CheckItem("C5", "必备结构", "PASS", "必备小节齐全")


def check_false_claims(text: str, mode: str = "draft") -> CheckItem:
    """不实陈述。mode=final 时放宽（成品可以写"已过闸门"）。"""
    hits = []
    for pat, msg in FALSE_CLAIM_PATTERNS:
        for m in re.finditer(pat, text):
            snippet = text[max(0, m.start() - 30): m.end() + 30].replace("\n", " ")
            if mode == "final":
                if re.search(r"提交|待审|以审校后版本为准|尚未", snippet):
                    hits.append(f"L{_line_of(text, m.start())} 自相矛盾：{m.group(0)}")
                continue
            hits.append(f"L{_line_of(text, m.start())} {m.group(0)} — {msg}")
    if hits:
        return CheckItem("C6", "不实陈述", "FAIL", f"{len(hits)} 处", hits)
    return CheckItem("C6", "不实陈述", "PASS", f"无（mode={mode}）")


def run_precheck(
    path: str,
    *,
    extra_words: tuple[str, ...] = (),
    supplied_weights: dict[str, float] | None = None,
    mode: str = "draft",
) -> list[CheckItem]:
    """对一份报告跑全部自检项。"""
    text = Path(path).read_text(encoding="utf-8-sig")
    return [
        check_intro(text),
        check_spoiler(text, extra_words),
        check_duplicate(text, extra_words),
        check_weights(text, supplied_weights),
        check_sections(text),
        check_false_claims(text, mode),
    ]


def format_report(items: list[CheckItem], path: str) -> str:
    icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}
    lines = [f"=== 送审前自检：{Path(path).name} ===", ""]
    n_fail = n_warn = 0
    for it in items:
        lines.append(f"{icon[it.status]} {it.code} {it.name}：{it.message}")
        if it.status == "FAIL":
            n_fail += 1
        elif it.status == "WARN":
            n_warn += 1
        for d in it.detail[:12]:
            lines.append(f"        - {d}")
    lines.append("")
    lines.append(f"汇总：{n_fail} FAIL / {n_warn} WARN / {len(items) - n_fail - n_warn} PASS")
    if n_fail:
        lines.append("→ 改完再送人工审校（这些是程序能查的）")
    elif n_warn:
        lines.append("→ 无硬性阻断，请逐条看过 WARN")
    else:
        lines.append("→ 可以进入人工审校")
    return "\n".join(lines)
