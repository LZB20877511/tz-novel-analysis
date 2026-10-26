"""TZ Novel Analysis 命令行入口。

    tznovel stats  <file.json|file.txt>     文风量化
    tznovel person <file.json|file.txt>     叙事人称判定
    tznovel premise <file.json|file.txt>    题材前提验证
    tznovel fetch  <url>                    抓取单页并提取正文
    tznovel probe  <url...>                 源可达性探测
    tznovel check  <report.md>              报告送审前自检
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tznovel import __version__


def _load_chapters(path: str) -> list[dict]:
    """载入章节数据。

    支持两种格式：
      1. JSON 数组/对象，元素含 body/text/title/label
      2. 纯文本（整篇当 1 章）
    """
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] 文件不存在：{path}", file=sys.stderr)
        raise SystemExit(2)

    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            # 可能是 {"chapters": [...]} 或单章对象
            data = data.get("chapters", [data])
        out = []
        for i, ch in enumerate(data):
            if not isinstance(ch, dict):
                out.append({"label": str(i + 1), "title": "", "body": str(ch)})
                continue
            out.append({
                "label": str(ch.get("label") or ch.get("seq") or ch.get("num") or i + 1),
                "title": str(ch.get("title") or ch.get("name") or ""),
                "body": ch.get("body") or ch.get("text") or "",
            })
        return out

    return [{"label": "1", "title": p.name, "body": p.read_text(encoding="utf-8-sig", errors="replace")}]


def cmd_stats(args) -> int:
    from tznovel.analyze.stats import analyze_text

    chapters = _load_chapters(args.file)
    r = analyze_text(chapters)

    print(f"=== 文风量化：{len(r.chapters)} 章 / {r.total_chars} 字 ===\n")
    print(f"  平均句长     {r.avg_sent} 字")
    print(f"  段落均长     {r.avg_para} 字")
    print(f"  对话句占比   {r.dlg_sent_pct}%")
    print(f"  对话字数占比 {r.dlg_char_pct}%")
    print(f"  「！」       {r.excl_per_k}/千字")
    print(f"  「？」       {r.quest_per_k}/千字")
    print(f"  省略号       {r.ellipsis_per_k}/千字")
    print(f"  长句≥60字    {r.long60_pct}%")
    print(f"  短句≤15字    {r.short15_pct}%")
    print(f"  pua 字符     {r.pua}")
    print(f"  latin 串     {r.latin} ({r.latin_per_k}/千字)")

    if r.question_beats_exclaim:
        print("\n  ★ 问号 > 感叹号：少见的叙述指纹（反问式幽默 / 克制叙述）")

    print(f"\n  廉价转折 A 组 {r.cheap_a_total} 次 —— {dict(r.cheap_a) or '无'}")
    print(f"  廉价转折 B 组 {r.cheap_b_total} 次 —— {dict(r.cheap_b) or '无'}")
    print(f"  手法信号词   {dict(list(r.signal_words.items())[:8]) or '无'}")
    print(f"  说话动词     {dict(list(r.speech_verbs.items())[:8]) or '无'}")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(r.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[OK] json → {args.json_out}")
    return 0


def cmd_person(args) -> int:
    from tznovel.analyze.person import detect_person

    chapters = _load_chapters(args.file)
    v = detect_person(chapters)

    print(f"=== 叙事人称判定 ===\n")
    print(f"  叙述句 {v.narr_sents} 句，其中以「我」作主语 {v.first_person_sents} 句")
    print(f"  占比   {v.ratio_pct}%")
    print(f"  判定   {v.verdict}（置信度 {v.confidence}）")
    if v.samples:
        print("\n  证据：")
        for s in v.samples:
            print(f"    「{s}」")

    print(f"\n  阈值说明：≥15% 判第一人称；<5% 判第三人称（实测锚点 0.1% vs 27.5%）")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(v.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[OK] json → {args.json_out}")
    return 0


def cmd_premise(args) -> int:
    from tznovel.analyze.premise import check_premise

    chapters = _load_chapters(args.file)
    r = check_premise(chapters)

    print(f"=== 题材前提验证 ===\n")
    print(f"  现代词 {r.modern_total} 次（{r.modern_per_k}/千字）")
    print(f"  修行词 {r.cultivation_total} 次（{r.cultivation_per_k}/千字）")
    print(f"  现代词占比 {r.modern_share_pct}%")
    print(f"\n  首次现代词位置 {r.first_modern_pos if r.first_modern_pos >= 0 else '未出现'}")
    print(f"  首次修行词位置 {r.first_cultivation_pos if r.first_cultivation_pos >= 0 else '未出现'}")
    print(f"  首次跨界词位置 {r.first_otherworld_pos if r.first_otherworld_pos >= 0 else '未出现'}")
    print(f"\n  跃迁判定：{r.transition}")
    if r.transition_detail:
        print(f"            {r.transition_detail}")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(r.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[OK] json → {args.json_out}")
    return 0


def cmd_fetch(args) -> int:
    from tznovel.fetch.extract import extract_body
    from tznovel.fetch.retry import Fetcher

    f = Fetcher()
    r = f.get(args.url, referer=args.referer)

    print(f"=== 抓取：{args.url} ===\n")
    print(f"  HTTP {r.status}  |  {r.reason}")
    print(f"  使用 UA：{f.last_ua}")
    if not r.ok:
        print(f"\n  ❌ 失败：{r.error.name if r.error else '未知'}")
        print(f"  建议：{r.suggested_action}")
        return 1

    ex = extract_body(r.text)
    print(f"  正文字数 {ex.chars}  |  段落 {ex.paragraphs}")
    print(f"  提取规则 {ex.matched_pattern}")
    print(f"  字符健康 pua={r.pua} U+FFFD={r.ufffd}")

    if args.save and ex.ok:
        Path(args.save).write_text(ex.body, encoding="utf-8")
        print(f"\n[OK] 正文 → {args.save}")
    if args.preview:
        print("\n--- 前 500 字 ---")
        print(ex.body[:500])
    return 0 if ex.ok else 1


def cmd_probe(args) -> int:
    from tznovel.fetch.retry import Fetcher

    f = Fetcher()
    ok_count = 0
    print(f"=== 源探测：{len(args.urls)} 个 ===\n")
    for u in args.urls:
        r = f.get(u)
        mark = "✅" if r.ok else "❌"
        print(f"{mark} {u}")
        print(f"   {r.reason} | UA={f.last_ua} | 正文{r.text_chars}字")
        if r.ok:
            ok_count += 1
        elif r.error:
            print(f"   建议：{r.suggested_action}")
    print(f"\n汇总：{ok_count}/{len(args.urls)} 可用")
    return 0 if ok_count else 1


def cmd_check(args) -> int:
    from tznovel.report.precheck import run_precheck, format_report

    results = run_precheck(args.file)
    print(format_report(results, args.file))
    fails = [r for r in results if r.status == "FAIL"]
    return 1 if (fails and args.strict) else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tznovel",
        description="TZ Novel Analysis — 网文阅读分析：读完再说，说必有据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--version", action="version", version=f"tznovel {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("stats", help="文风量化")
    p.add_argument("file")
    p.add_argument("--json-out", default="")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("person", help="叙事人称判定")
    p.add_argument("file")
    p.add_argument("--json-out", default="")
    p.set_defaults(func=cmd_person)

    p = sub.add_parser("premise", help="题材前提验证")
    p.add_argument("file")
    p.add_argument("--json-out", default="")
    p.set_defaults(func=cmd_premise)

    p = sub.add_parser("fetch", help="抓取单页并提取正文")
    p.add_argument("url")
    p.add_argument("--referer", default="")
    p.add_argument("--save", default="")
    p.add_argument("--preview", action="store_true")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("probe", help="源可达性探测")
    p.add_argument("urls", nargs="+")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("check", help="报告送审前自检")
    p.add_argument("file")
    p.add_argument("--strict", action="store_true")
    p.set_defaults(func=cmd_check)

    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
