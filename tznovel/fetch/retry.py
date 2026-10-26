"""带降级的抓取器：UA 轮换 + 错误分类 + 自动重试。

降级顺序（按实测性价比排序，成本从低到高）：

    1. PC UA 直取
    2. 换移动 UA（实测最有效：某站 PC→403、移动→200）
    3. 退避重试（应对 5xx / 偶发超时）
    4. 判定为站点无内容 → 直接放弃换源（不要浪费轮次）

⚠️ 不支持：验证码绕过、付费墙突破。遇墙即停并如实报告。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from tznovel.fetch.base import (
    FetchError,
    FetchResult,
    classify,
    decode_bytes,
    extract_plain,
    inspect_text,
)
from tznovel.fetch.ua_pool import profiles as ua_profiles


@dataclass
class FetcherConfig:
    """抓取配置。"""

    timeout: int = 25
    max_retries: int = 2
    retry_backoff: float = 2.0
    delay_between: float = 1.2
    try_all_uas: bool = True
    min_chars: int = 500


@dataclass
class Fetcher:
    """带 UA 降级的抓取器。

    Example:
        >>> f = Fetcher()
        >>> r = f.get("https://example.com/chapter/1.html")
        >>> r.ok
        True
    """

    config: FetcherConfig = field(default_factory=FetcherConfig)
    _session: object = None
    last_ua: str = ""

    def __post_init__(self):
        try:
            import requests  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ImportError("需要 requests：pip install requests") from e
        self._session = None

    def _get_once(self, url: str, ua_profile, referer: str = "") -> FetchResult:
        import requests

        try:
            r = requests.get(
                url,
                headers=ua_profile.headers(referer),
                timeout=self.config.timeout,
                allow_redirects=True,
            )
        except Exception as e:
            return FetchResult(
                url=url, ok=False, error=FetchError.NETWORK,
                reason=f"{type(e).__name__}: {e}",
            )

        text, enc, memo = decode_bytes(r.content)
        err, reason = classify(r.status_code, text, min_chars=self.config.min_chars)
        plain = extract_plain(text)
        health = inspect_text(plain)

        res = FetchResult(
            url=url,
            ok=False,
            status=r.status_code,
            text=text,
            bytes_len=len(r.content),
            error=err,
            reason=reason,
            pua=health["pua"],
            ufffd=health["ufffd"],
            text_chars=len(plain.strip()),
            encoding_used=enc,
            encoding_memo=memo,
        )

        if err is None and not health["usable"]:
            res.error = FetchError.ENCODING_BAD
            res.reason = (
                f"正文不可用（pua={health['pua']}, U+FFFD={health['ufffd']}, "
                f"首行可读={health['head_readable']}）"
            )
            return res

        if err is None:
            res.ok = True
        return res

    def get(self, url: str, *, referer: str = "") -> FetchResult:
        """抓取一个 URL，自动按 UA 池降级。"""
        profiles = ua_profiles()
        if not self.config.try_all_uas:
            profiles = profiles[:1]

        last: FetchResult | None = None
        for prof in profiles:
            res = self._get_once(url, prof, referer)
            self.last_ua = prof.name
            last = res

            if res.ok:
                return res

            # 站点自身无内容 / 页面不存在 → 换 UA 也没用，立即返回
            if res.error in (FetchError.EMPTY_SITE, FetchError.FATAL):
                return res

            # 网络错误 → 退避重试同一 UA
            if res.error in (FetchError.NETWORK, FetchError.RETRYABLE):
                for attempt in range(self.config.max_retries):
                    time.sleep(self.config.retry_backoff * (attempt + 1))
                    res = self._get_once(url, prof, referer)
                    if res.ok:
                        return res
                    if res.error not in (FetchError.NETWORK, FetchError.RETRYABLE):
                        break
                last = res
                continue

            # IP_BLOCKED / ENCODING_BAD / UNKNOWN → 换下一个 UA
            time.sleep(self.config.delay_between * 0.5)

        return last or FetchResult(url=url, ok=False, error=FetchError.UNKNOWN, reason="无结果")

    def get_many(self, urls: list[str], *, referer: str = "") -> list[FetchResult]:
        """批量抓取，自动间隔。失败不抛异常，逐条返回。"""
        out = []
        for i, u in enumerate(urls):
            out.append(self.get(u, referer=referer))
            if i < len(urls) - 1:
                time.sleep(self.config.delay_between)
        return out
