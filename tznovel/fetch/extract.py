"""通用正文提取与清洗。

不绑定任何特定站点 —— 按启发式规则找正文容器，找不到则用文本密度兜底。
站点专用适配器（sources/）在需要时覆盖本模块的行为。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 常见小说站正文容器（按命中率排序）
CONTENT_PATTERNS: tuple[str, ...] = (
    r'(?s)<div[^>]*id="content"[^>]*>(.*?)</div>',
    r'(?s)<div[^>]*id="chaptercontent"[^>]*>(.*?)</div>',
    r'(?s)<div[^>]*id="booktext"[^>]*>(.*?)</div>',
    r'(?s)<div[^>]*class="[^"]*(?:content|article|chapter)[^"]*"[^>]*>(.*?)</div>',
    r'(?s)<article[^>]*>(.*?)</article>',
)

# 需要剥离的内嵌广告块（部分站点把广告塞在正文 div 里）
AD_BLOCK_PATTERNS: tuple[str, ...] = (
    r'(?s)<div[^>]*id="center_tip"[^>]*>.*?</div>',
    r'(?s)<div[^>]*class="[^"]*ads?[^"]*"[^>]*>.*?</div>',
    r'(?s)<script[^>]*>.*?</script>',
    r'(?s)<style[^>]*>.*?</style>',
)

# 站点噪声行（导航、求票、水印）
JUNK_PATTERNS: tuple[str, ...] = (
    r"^上一[章页]", r"^下一[章页]", r"^返回目录", r"^章节目录", r"^加入书签",
    r"^投推荐票", r"^请记住本站", r"^最新网址", r"^天才一秒", r"^手机版",
    r"^本站", r"^全文阅读", r"^章节报错", r"^加入书架", r"^举报",
    r"\.com", r"\.net", r"www\.", r"^https?://",
    r"^\(\s*未完待续", r"^（\s*未完待续", r"^本章完",
    r"^第[一二三四五六七八九十0-9]+更", r"^求[月推]票",
)


@dataclass
class ExtractResult:
    """正文提取结果。"""

    body: str = ""
    chars: int = 0
    paragraphs: int = 0
    matched_pattern: str = ""
    stripped_ads: int = 0
    stripped_junk: int = 0

    @property
    def ok(self) -> bool:
        return self.chars >= 300


def _strip_blocks(html: str) -> tuple[str, int]:
    n = 0
    for pat in AD_BLOCK_PATTERNS:
        html, k = re.subn(pat, "", html)
        n += k
    return html, n


def _to_text(fragment: str) -> str:
    t = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    t = re.sub(r"(?i)</p>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    t = t.replace("\u3000", " ")  # 全角空格
    return t


def _clean_lines(text: str) -> tuple[str, int]:
    lines = []
    dropped = 0
    for raw in text.split("\n"):
        s = raw.strip()
        if not s:
            continue
        if len(s) < 4:
            dropped += 1
            continue
        if any(re.search(p, s, re.I) for p in JUNK_PATTERNS):
            dropped += 1
            continue
        lines.append(s)
    return "\n".join(lines), dropped


def extract_body(html: str, *, min_chars: int = 300) -> ExtractResult:
    """从 HTML 提取正文。

    Args:
        html: 页面源码
        min_chars: 低于此字数视为提取失败

    Returns:
        ExtractResult
    """
    cleaned, n_ads = _strip_blocks(html or "")

    for pat in CONTENT_PATTERNS:
        m = re.search(pat, cleaned)
        if not m:
            continue
        text, dropped = _clean_lines(_to_text(m.group(1)))
        # 短对白多的书可能段落短，用字符数判断而非行数
        if len(text) >= min_chars:
            return ExtractResult(
                body=text,
                chars=len(text),
                paragraphs=text.count("\n") + 1,
                matched_pattern=pat,
                stripped_ads=n_ads,
                stripped_junk=dropped,
            )

    # 兜底：整页按行取长文本
    text, dropped = _clean_lines(_to_text(cleaned))
    keep = [ln for ln in text.split("\n") if len(ln) >= 12]
    body = "\n".join(keep)
    return ExtractResult(
        body=body,
        chars=len(body),
        paragraphs=len(keep),
        matched_pattern="<fallback:line-density>",
        stripped_ads=n_ads,
        stripped_junk=dropped,
    )
