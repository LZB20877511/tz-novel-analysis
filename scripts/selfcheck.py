#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
selfcheck.py — 上架前自检（v1.0）

为什么需要它：
    第一次上架开源项目时，最容易犯的错**都不是代码错**，而是：
      · README 里写了 `pip install xxx`，但包没发布到 PyPI（照做必失败）
      · 文档内部链接指向不存在的文件
      · 文档引用已被重命名的脚本
      · CI 徽章显示红色（Windows runner 中文输出崩溃）
      · Issue 模板里的相对路径层级算错
      · 版本号三处不一致

    这些机器都能查，不该靠人记。

用法：
    python scripts/selfcheck.py            # 全部检查
    python scripts/selfcheck.py --json     # 机器可读输出

退出码：0 全通过；1 有 FAIL
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 不应出现在公开仓库里的内容
SENSITIVE = [
    ("本机用户名", r"\bLZB11\b"),
    ("真实姓名ID", r"lzb\d{8}"),  # 模式化，避免自检脚本自身变成泄露源
    ("GitHub Token", r"github_pat_[A-Za-z0-9_]{20,}"),
    ("Gitee Token", r"\b[0-9a-f]{32}\b"),
    ("Cloudflare Token", r"cfat_[A-Za-z0-9]{20,}"),
    ("OpenRouter Key", r"sk-or-v1-[A-Za-z0-9]{20,}"),
    ("本机绝对路径", r"C:\\Users\\[A-Za-z]"),
]

SKIP_DIRS = {".git", "__pycache__", "build", "dist", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", "htmlcov"}


class Result:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, code: str, name: str, status: str, msg: str, detail=None):
        self.items.append({"code": code, "name": name, "status": status,
                           "msg": msg, "detail": detail or []})

    @property
    def failed(self):
        return [i for i in self.items if i["status"] == "FAIL"]

    def report(self) -> str:
        icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}
        lines = ["=== 上架前自检 ===", ""]
        for it in self.items:
            lines.append(f"{icon[it['status']]} {it['code']} {it['name']}：{it['msg']}")
            for d in it["detail"][:10]:
                lines.append(f"        - {d}")
        n_fail = len(self.failed)
        n_warn = sum(1 for i in self.items if i["status"] == "WARN")
        lines.append("")
        lines.append(f"汇总：{n_fail} FAIL / {n_warn} WARN / "
                     f"{len(self.items) - n_fail - n_warn} PASS")
        if n_fail:
            lines.append("→ 有硬性阻断，修完再发布")
        else:
            lines.append("→ 可以发布")
        return "\n".join(lines)


def walk_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not any(s in p.parts for s in SKIP_DIRS):
            yield p


def check_version(r: Result):
    """C1 版本号三处一致。"""
    pyproject = ROOT / "pyproject.toml"
    init = ROOT / "tznovel" / "__init__.py"
    changelog = ROOT / "CHANGELOG.md"
    vals = {}
    if pyproject.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        vals["pyproject"] = m.group(1) if m else None
    if init.exists():
        m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
        vals["__init__"] = m.group(1) if m else None
    if changelog.exists():
        m = re.search(r"^##\s*\[([\d.]+)\]", changelog.read_text(encoding="utf-8"), re.M)
        vals["CHANGELOG"] = m.group(1) if m else None

    uniq = set(v for v in vals.values() if v)
    detail = [f"{k} = {v}" for k, v in vals.items()]
    if len(uniq) == 1:
        r.add("C1", "版本号一致", "PASS", f"{uniq.pop()}", detail)
    else:
        r.add("C1", "版本号一致", "FAIL", f"不一致：{uniq}", detail)


def check_sensitive(r: Result):
    """C2 无敏感信息（本机路径 / 令牌 / 用户名）。"""
    hits = []
    for p in walk_files():
        if p.suffix.lower() in {".json"} and "examples" in p.parts:
            continue  # 样本数据单独判断
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pat in SENSITIVE:
            for m in re.finditer(pat, txt):
                # 白名单：.gitignore / 文档里作为"规则示例"出现的
                line_start = txt.rfind("\n", 0, m.start()) + 1
                line = txt[line_start: txt.find("\n", m.start()) if "\n" in txt[m.start():] else len(txt)]
                if any(k in line for k in ("secrets/", "*.token", "示例", "例如", "不要提交")):
                    continue
                hits.append(f"{p.relative_to(ROOT)} [{label}] {m.group(0)[:30]}")
    if hits:
        r.add("C2", "敏感信息", "FAIL", f"{len(hits)} 处", hits)
    else:
        r.add("C2", "敏感信息", "PASS", "无本机路径/令牌/用户名")


def check_links(r: Result):
    """C3 文档内部链接有效。"""
    broken = []
    for p in ROOT.rglob("*.md"):
        if ".git" in p.parts:
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\]\((?!http|#|mailto)([^\)#]+\.md)", txt):
            target = m.group(1)
            if not (p.parent / target).resolve().exists():
                broken.append(f"{p.relative_to(ROOT)} → {target}")
    if broken:
        r.add("C3", "内部链接", "FAIL", f"{len(broken)} 个死链", broken)
    else:
        r.add("C3", "内部链接", "PASS", "全部有效")


def check_stale_refs(r: Result):
    """C4 无已废弃的脚本名引用。

    注意：只检查「看起来像命令或路径引用」的行，
    排除「说明性文字」（例如自检工具自己的说明、CHANGELOG 的历史记录）。
    """
    stale = ["novel_stats.py", "precheck.py", "source_probe.py",
             "premise_check.py", "fetch_mobile_ua.py"]
    # 说明性上下文的特征词 —— 出现这些就跳过该行
    EXPLANATORY = ("已废弃", "已重命名", "旧脚本", "不要用", "改为", "→",
                   "selfcheck", "CHANGELOG", "历史")
    hits = []
    for p in ROOT.rglob("*.md"):
        if ".git" in p.parts:
            continue
        for lineno, line in enumerate(
                p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
            if not any(s in line for s in stale):
                continue
            if any(k in line for k in EXPLANATORY):
                continue
            # 只报「像命令/路径」的行：含 python / scripts/ / scripts\\ / 反引号包裹
            looks_like_ref = ("scripts" in line or "python " in line
                              or line.strip().startswith("-"))
            if looks_like_ref:
                hits.append(f"{p.relative_to(ROOT)}:L{lineno} → {line.strip()[:60]}")
    if hits:
        r.add("C4", "废弃引用", "WARN", f"{len(hits)} 处仍在引用旧脚本名", hits)
    else:
        r.add("C4", "废弃引用", "PASS", "无")


def check_pypi_claim(r: Result):
    """C5 README 的安装命令是否与发布状态一致。

    这是实测踩过的坑：README 写 `pip install tznovel`，
    但包没发布到 PyPI —— 照做的人 100% 失败。
    """
    readme = ROOT / "README.md"
    if not readme.exists():
        r.add("C5", "安装命令", "SKIP", "无 README")
        return
    txt = readme.read_text(encoding="utf-8")
    name = "tznovel"
    has_bare = bool(re.search(rf"^pip install {name}\s*$", txt, re.M))
    disclaims = "尚未发布到 PyPI" in txt or "not.*published" in txt.lower()
    if has_bare and not disclaims:
        r.add("C5", "安装命令", "FAIL",
              f"写了 `pip install {name}` 但未声明包未发布 PyPI", [])
    elif has_bare and disclaims:
        r.add("C5", "安装命令", "WARN", "有裸 pip install，但已加说明", [])
    else:
        r.add("C5", "安装命令", "PASS", "与发布状态一致")


def check_required_files(r: Result):
    """C6 必备文件齐全。"""
    required = {
        "README.md": True, "LICENSE": True, "pyproject.toml": True,
        "CHANGELOG.md": False, "CONTRIBUTING.md": False,
        "SECURITY.md": False, ".gitignore": True,
    }
    missing_hard, missing_soft = [], []
    for f, hard in required.items():
        if not (ROOT / f).exists():
            (missing_hard if hard else missing_soft).append(f)
    if missing_hard:
        r.add("C6", "必备文件", "FAIL", f"缺关键文件：{missing_hard}", missing_hard)
    elif missing_soft:
        r.add("C6", "必备文件", "WARN", f"缺可选文件：{missing_soft}", missing_soft)
    else:
        r.add("C6", "必备文件", "PASS", f"{len(required)} 项齐全")


def check_py_bom(r: Result):
    """C7 Python 文件无 BOM。

    BOM 会导致 SyntaxError: invalid non-printable character U+FEFF。
    （这是本项目实测踩过的坑，PowerShell 的 Out-File -Encoding UTF8 会加 BOM）
    """
    bad = []
    for p in ROOT.rglob("*.py"):
        if any(s in p.parts for s in SKIP_DIRS):
            continue
        raw = p.read_bytes()[:3]
        if raw == b"\xef\xbb\xbf":
            bad.append(str(p.relative_to(ROOT)))
    if bad:
        r.add("C7", "py 无 BOM", "FAIL", f"{len(bad)} 个文件带 BOM", bad)
    else:
        r.add("C7", "py 无 BOM", "PASS", "全部无 BOM")


def check_no_novel_text(r: Result):
    """C8 仓库不含整本小说正文（版权合规）。"""
    big = []
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".txt", ".json"}:
            if any(s in p.parts for s in SKIP_DIRS):
                continue
            size = p.stat().st_size
            if size > 60_000:  # 60KB 以上的文本文件视为可疑
                big.append(f"{p.relative_to(ROOT)} ({size // 1024} KB)")
    if big:
        r.add("C8", "正文合规", "WARN", f"{len(big)} 个大文本文件，确认非整本正文", big)
    else:
        r.add("C8", "正文合规", "PASS", "无大体积文本文件")


def check_encoding_safety(r: Result):
    """C9 CLI 是否有 Windows 中文输出保护。

    Windows 控制台默认 cp936，直接 print 中文会 UnicodeEncodeError。
    这个坑在 CI 上表现为 windows job 全红。
    """
    cli = ROOT / "tznovel" / "cli.py"
    if not cli.exists():
        r.add("C9", "编码安全", "SKIP", "无 cli.py")
        return
    txt = cli.read_text(encoding="utf-8")
    has_guard = "_force_utf8_stdio" in txt and 'reconfigure(encoding="utf-8"' in txt
    if has_guard:
        r.add("C9", "编码安全", "PASS", "CLI 已强制 UTF-8 输出")
    else:
        r.add("C9", "编码安全", "WARN",
              "CLI 未设 UTF-8 保护 → Windows 上中文输出可能崩溃", [])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="上架前自检")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args(argv)

    r = Result()
    for fn in (check_version, check_sensitive, check_links, check_stale_refs,
               check_pypi_claim, check_required_files, check_py_bom,
               check_no_novel_text, check_encoding_safety):
        try:
            fn(r)
        except Exception as e:
            r.add("ERR", fn.__name__, "FAIL", f"检查器异常：{e}")

    if args.json:
        print(json.dumps(r.items, ensure_ascii=False, indent=2))
    else:
        print(r.report())
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
