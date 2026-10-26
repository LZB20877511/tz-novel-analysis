"""统一抓取接口与错误分类。

设计来源：吸收 spider 技能中"错误分类驱动降级"的思想，但重写为小说场景专用：

    不同错误 → 不同动作，而不是一律 retry
    
    FATAL        → 停止，换源（404/410/451，页面不存在）
    RETRYABLE    → 重试（超时 / 5xx）
    IP_BLOCKED   → 换 IP 或换 UA（403 且响应体是拦截特征）
    RATE_LIMIT   → 慢下来（429）
    EMPTY_SITE   → 换源（站点自身无内容，如"转码失败"）
    ENCODING_BAD → 重抓（整章乱码，U+FFFD 占比高）

关键教训（实测）：**pua 低 ≠ 正文干净。**
    某站页面混入 1 个非法字节，整章被当 GBK 解码 → 全乱码，
    而 pua 只报 5%，按"pua>50 才判字体加密"的旧阈值会误判为"轻度可用"。
    本模块因此同时校验 pua 与 U+FFFD。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class FetchError(str, Enum):
    """抓取失败类型。"""

    FATAL = "fatal"                 # 404/410/451，换源
    RETRYABLE = "retryable"         # 超时/5xx，重试
    IP_BLOCKED = "ip_blocked"       # 403 + 拦截特征
    RATE_LIMIT = "rate_limit"       # 429
    EMPTY_SITE = "empty_site"       # 站点自身无内容
    ENCODING_BAD = "encoding_bad"   # 编码错乱
    NETWORK = "network"             # 连接失败
    UNKNOWN = "unknown"


# 站点"自身无内容"的明确标记 —— 命中就换源，爬虫再强也没用
EMPTY_MARKERS: tuple[str, ...] = (
    "转码失败", "请换源", "本章内容已下架", "内容不存在", "该章节不存在",
    "章节已删除", "本书已下架",
)

# 拦截页特征
BLOCK_MARKERS: tuple[str, ...] = (
    "just a moment", "checking your browser", "attention required",
    "enable javascript and cookies", "cf-browser-verification",
    "验证你不是机器人", "人机验证", "请开启javascript", "访问被拒绝",
    "access denied", "403 forbidden",
)

DEAD_CODES = {404, 410, 451}
RETRY_CODES = {500, 502, 503, 504}


@dataclass
class FetchResult:
    """一次抓取的结果（成功或失败都返回，不抛异常）。"""

    url: str = ""
    ok: bool = False
    status: int | None = None
    text: str = ""
    bytes_len: int = 0
    error: FetchError | None = None
    reason: str = ""
    pua: int = 0
    ufffd: int = 0
    text_chars: int = 0
    encoding_used: str = ""
    encoding_memo: dict = field(default_factory=dict)

    @property
    def suggested_action(self) -> str:
        """根据错误类型给出下一步动作。"""
        return {
            FetchError.FATAL: "换源（页面不存在）",
            FetchError.RETRYABLE: "重试（服务端临时错误）",
            FetchError.IP_BLOCKED: "换 UA 或换 IP（WAF/Cloudflare 拦截）",
            FetchError.RATE_LIMIT: "降低频率后重试",
            FetchError.EMPTY_SITE: "换源（站点自身无内容，非反爬）",
            FetchError.ENCODING_BAD: "重抓（编码错乱）",
            FetchError.NETWORK: "检查网络后重试",
            FetchError.UNKNOWN: "人工检查",
        }.get(self.error, "")


RE_PUA = re.compile(r"[\uE000-\uF8FF]")
RE_TAG = re.compile(r"(?s)<[^>]+>")
RE_SCRIPT = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")


def decode_bytes(raw: bytes) -> tuple[str, str, dict]:
    """解码字节，返回 (文本, 编码名, 诊断信息)。

    策略：先宽松 UTF-8，若替换符占比 >2% 再试 gb18030，取更干净者。
    绝不"抛异常就整体换编码"（那会导致整章乱码）。
    """
    memo: dict = {}
    try:
        u = raw.decode("utf-8", errors="replace")
    except Exception:
        u = ""

    bad_u = u.count("\ufffd")
    memo["utf8_ufffd"] = bad_u
    memo["utf8_len"] = len(u)
    ratio_u = bad_u / len(u) if u else 1.0

    if ratio_u > 0.02:
        try:
            g = raw.decode("gb18030", errors="replace")
            bad_g = g.count("\ufffd")
            memo["gbk_ufffd"] = bad_g
            ratio_g = bad_g / len(g) if g else 1.0
            if ratio_g < ratio_u:
                return g, "gb18030", memo
        except Exception:
            memo["gbk_error"] = True

    return u, "utf-8", memo


def extract_plain(html: str) -> str:
    """粗暴去标签，用于字数估算。"""
    t = RE_SCRIPT.sub("", html or "")
    t = RE_TAG.sub("", t)
    return t


def classify(
    status: int | None,
    html: str,
    *,
    min_chars: int = 500,
) -> tuple[FetchError | None, str]:
    """对一次响应分类。返回 (错误类型, 说明)；无错误返回 (None, 说明)。"""
    body = html or ""
    low = body.lower()
    n = len(extract_plain(body))

    if status in DEAD_CODES:
        return FetchError.FATAL, f"HTTP {status}（页面不存在）"

    for m in EMPTY_MARKERS:
        if m in body:
            return FetchError.EMPTY_SITE, f"含「{m}」→ 站点自身无内容，换源"

    hit = [m for m in BLOCK_MARKERS if m in low]
    if status == 403 or hit:
        return FetchError.IP_BLOCKED, f"拦截特征：{hit[:2] or ['HTTP 403']}"

    if status == 429:
        return FetchError.RATE_LIMIT, "HTTP 429（请求过快）"

    if status in RETRY_CODES:
        return FetchError.RETRYABLE, f"HTTP {status}（服务端临时错误）"

    if n < min_chars:
        # ⚠️ 短页面不等于被拦截。实测踩过：example.com 只有 171 字，
        # 被误报成 IP_BLOCKED，用户会以为被封了。
        # 只有出现拦截特征词或明确状态码时才判 IP_BLOCKED，否则判"内容不足"。
        if hit:
            return FetchError.IP_BLOCKED, f"正文过短且含拦截特征（{n} 字）"
        return FetchError.EMPTY_SITE, (
            f"页面内容过短（{n} 字，阈值 {min_chars}）——"
            f"可能不是正文页/需要登录/该页确实很简短"
        )

    return None, f"正文 {n} 字"


def inspect_text(text: str) -> dict:
    """检查文本健康度：pua / U+FFFD / 首行是否可读。

    这是"能不能拿来分析"的最终判据 —— pua 低不代表干净。
    """
    pua = len(RE_PUA.findall(text or ""))
    ufffd = (text or "").count("\ufffd")
    head = (text or "").strip()[:80]
    # 首行出现连续替换符或乱码 → 判定不可用
    head_bad = head.count("\ufffd") >= 3 or "锟斤拷" in head
    return {
        "pua": pua,
        "ufffd": ufffd,
        "head": head,
        "head_readable": not head_bad,
        "usable": pua == 0 and ufffd == 0 and not head_bad,
    }
