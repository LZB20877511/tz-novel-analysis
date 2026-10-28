# TZ Novel Analysis · Web Novel Reading Analysis

> **Read it first, then judge. Every claim must have evidence.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-54%20passed-brightgreen)](tests/)

English (current) ｜ [中文](README.md)

A toolkit for **evaluating Chinese web novels** (网文) after actually reading them —
not predicting whether you will like a book, but producing a **verifiable review**
once the text has been read.

> ⚠️ **Maintenance status: no scheduled updates, no guaranteed issue response.**
> This is a personal tool open-sourced as-is. If you need ongoing maintenance, fork it.
> See [MAINTENANCE.md](MAINTENANCE.md).

---

## The problem it solves

Most "novel recommendation" tools work **before** you read: rankings, genre trends, popularity scores.
This project works **after** you read: how do you form a judgment that someone else can check?

Real failure modes it addresses:

| Problem | What this project does |
|---|---|
| "The prose is good" — but the reviewer never read it | Requires real text as evidence |
| Aggregated star ratings hide disagreement | Dual-track: model's own score **alongside** external consensus, disagreement preserved |
| No one says how much they actually read | Mandatory coverage disclosure (chapters / characters / % of book) |
| Spoilers in summaries | Hard gate on endings, twists, pairings |
| Numbers that can't be reproduced | **Deterministic algorithms only** — no LLM inference, same input → same output |

---

## Three analysis modules

### `tznovel person` — Narrative person detection

Strips dialogue, then measures the share of narrative sentences whose subject is 「我」 (I).

Threshold 15%, based on measured anchors:

| Book | Measured | Verdict |
|---|---|---|
| 《茅山后裔》 | 0.1% | Third person |
| 《走进修仙》 | 0.1% | Third person |
| 《民调局异闻录》 sequel | 27.5%–36.4% | First person |

**Why it matters**: among books matching a genre request, roughly 60% may be first-person.
Many readers cannot stand it. This makes the check automatic.

### `tznovel premise` — Premise verification

Every genre tag online is human-entered, and **nobody verifies them**. Three real failures:

- A book tagged "urban → cultivation" had **93 characters** of modern setting, appearing after character 1000 — it is effectively "cultivation from page one"
- A book tagged "third person" was **first person throughout** ("My name is Shen La")
- A book tagged "has a transition" kept both worlds **in parallel**, never leaving the city

### `tznovel stats` — Prose metrics

Sentence length / paragraph length / dialogue ratio / punctuation density / diction frequency.
Cheap transition words are reported in **two separate groups** — reporting only group A
creates the illusion of "no template feel".

```
平均句长     51.5 字        对话字数占比 21.2%
「！」       2.0/千字       「？」       4.0/千字
长句≥60字    30.7%          短句≤15字    19.3%
```

---

## Install

```bash
git clone https://github.com/LZB20877511/tz-novel-analysis.git
cd tz-novel-analysis
pip install -e .
```

**Requirements**: Python 3.9+. Only runtime dependency is `requests`.
**No GPU, no API key, no LLM call, no database.**

> Not published to PyPI yet — do not `pip install tznovel`.

## Use

```bash
tznovel person  my_novel.txt      # narrative person
tznovel stats   my_novel.txt      # prose metrics
tznovel premise my_novel.txt      # genre premise check
tznovel check   report.md         # pre-submission self-check
```

Input can be a plain `.txt` or a JSON array of chapters.

---

## Six books analyzed (~399,000 characters actually read)

| Book | Genre | Self score | External |
|---|---|---|---|
| 史上第一祖师爷 | Fantasy | 6.7 | 6.6 |
| 寸芒 | Xianxia | 5.9 | 6.6 |
| 弹痕 | Military | 6.8 | 6.9–7.9 |
| 大王饶命 | Urban / light novel | 6.9 | 4.5–7.2 |
| 神游 | Urban cultivation | — | 8.4 / 8.1 |
| 茅山后裔 | Urban Taoist | — | 8.0 / 7.2 |

**Case study worth reading**: 《神游》 has 8.4 on Douban, yet a 76-upvote review calls its
writing "flat as boiled water". Both are right — one reviews the **quotation layer**
(classical allusions, erudition), the other the **narrative layer** (sentence-level craft).
Sharpest single piece of evidence: the author wrote 《庄子》's 「撚宁」 as 「樱宁」 four times,
including in a chapter title. The praisers saw "he knows the three passages";
the critics saw "he miscopied a character". Same spot, both judgments valid.

See [docs/CASE-STUDIES.md](docs/CASE-STUDIES.md) (Chinese).

---

## Fetch layer: error-classification-driven degradation

> **403 does not mean you need a headless browser.**

Measured on the same chapter page:

```
PC UA       →  HTTP 403, "403 Forbidden nginx"
Mobile UA   →  HTTP 200, 23,024 characters of text
```

Response headers `Server: cloudflare` + `cf-cache-status: BYPASS` show this is a
**WAF rule keyed on User-Agent**, not a JS challenge. Switching UA is enough.

Built-in UA pool: PC + 5 mobile profiles (iPhone / Android / WeChat / UC / Quark).

### Error taxonomy

| Type | Signal | Action |
|---|---|---|
| `FATAL` | 404 / 410 / 451 | Switch source |
| `EMPTY_SITE` | Page says "transcoding failed" | **Switch source — crawler cannot help** |
| `IP_BLOCKED` | 403 + block markers | Rotate UA / IP |
| `RATE_LIMIT` | 429 | Slow down |
| `RETRYABLE` | 5xx | Back off and retry |
| `ENCODING_BAD` | Garbled first line / high U+FFFD | Re-fetch |

### A trap worth knowing: low PUA ≠ clean text

One bad byte caused a whole chapter to be decoded as GBK — **total garbage** — while the
`pua` metric reported only **5%**. Under an old "pua > 50 means font-encryption" threshold
this would be misjudged as "slightly polluted, usable".

Decoding strategy here: lenient UTF-8 → check U+FFFD share > 2% → only then try gb18030.
**Never "catch the exception and switch encoding wholesale"** — that is exactly how the
garbage was produced.

---

## Report self-check

Three error classes occur **every single time**, and all are machine-checkable:

| Check | Content | Real record |
|---|---|---|
| C1 intro length | ≤120 chars, declared must equal actual | **Estimated by hand 4 times, wrong 4 times, always under-reported** |
| C2 spoiler scan | Endings / twists / culprit patterns | — |
| C3 duplicate sentence | Dangerous phrasing appearing ≥2 times | **Caught in 3 consecutive reports** |
| C4 weighted sum | Six-dimension weighted value vs claimed | Once claimed 5.90 vs actual 5.85 |
| C5 required sections | Conclusion / summary / coverage / evidence tags | — |
| C6 false claims | Draft claiming "gate passed" | Once wrote "unreviewed" as "passed" |

---

## Compliance boundary

**A personal analysis tool, not a reader.**

| ✅ Does | ❌ Does not |
|---|---|
| Analyze publicly readable chapters | Bypass paywalls / VIP |
| Sample a few chapters | Bulk-download whole books |
| Fetch public rankings / metadata | Solve CAPTCHAs |
| Local personal analysis | Redistribute full text |

**This repository contains no novel full text.**

---

## Docs

- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — runtime environment, Agent model (Chinese)
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) — two iron rules, nine practice rules (Chinese)
- [docs/CASE-STUDIES.md](docs/CASE-STUDIES.md) — six book analyses and lessons (Chinese)
- [docs/data/SOP.md](docs/data/SOP.md) — standard workflow (Chinese)

Most docs are in Chinese, as the subject matter is Chinese web novels.
The code, CLI, and docstrings are bilingual-friendly.

## License

[MIT](LICENSE)
