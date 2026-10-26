"""UA 池与轮换。

实测发现（2026-10）：**同一章节页，PC UA 与移动 UA 结果完全不同。**

    PC (Chrome 126)      → HTTP 403，响应体 "403 Forbidden nginx"
    iPhone Safari        → HTTP 200，23024 字正文

诊断：响应头 `Server: cloudflare` + `cf-cache-status: BYPASS`，
说明是 **WAF 按 UA 判定的规则**，不是 Cloudflare JS 挑战。
→ **换 UA 就过，不需要 camoufox。**

这条经验已固化为"先换 UA，再上重武器"的降级顺序。
"""

from __future__ import annotations

from dataclasses import dataclass

PC_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 移动 UA 池：小说站多为移动端优先建站，移动端反爬普遍更松
MOBILE_UAS: tuple[str, ...] = (
    # iPhone Safari
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
     "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
    # Android Chrome
    ("Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"),
    # 微信内置浏览器
    ("Mozilla/5.0 (Linux; Android 12; MI 11) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Version/4.0 Chrome/107.0.5304.141 Mobile Safari/537.36 "
     "MicroMessenger/8.0.40"),
    # UC 浏览器
    ("Mozilla/5.0 (Linux; U; Android 12; zh-CN; V2118A Build/SP1A.210812.003) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
     "Chrome/100.0.4896.58 UWS/15.0.8.1147 Mobile Safari/537.36 UCBS/15.0.8.1147_220"),
    # 夸克
    ("Mozilla/5.0 (Linux; Android 13; 22021211RC) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Version/4.0 Chrome/116.0.5845.163 Mobile Safari/537.36 "
     "Quark/7.5.6.393"),
)

ALL_UAS: tuple[str, ...] = (PC_CHROME,) + MOBILE_UAS


@dataclass
class UAProfile:
    """一组请求头配置。"""

    name: str
    ua: str
    is_mobile: bool = False

    def headers(self, referer: str = "") -> dict[str, str]:
        h = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if self.is_mobile:
            h["X-Requested-With"] = "com.quark.browser"
        if referer:
            h["Referer"] = referer
        return h


def profiles() -> list[UAProfile]:
    """按推荐尝试顺序返回 UA 配置：PC 先试，然后移动端逐个试。"""
    out = [UAProfile("pc-chrome", PC_CHROME, False)]
    names = ["mobile-iphone", "mobile-android", "mobile-wechat", "mobile-uc", "mobile-quark"]
    for name, ua in zip(names, MOBILE_UAS):
        out.append(UAProfile(name, ua, True))
    return out


# 说明：轮换顺序有讲究 —— PC 优先（多数站正常），
# 只有被拦时才逐个换移动端。这样正常站不会因为用移动 UA 而拿到降级页面。
