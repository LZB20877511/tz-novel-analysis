---
name: Bug 报告
about: 报告一个可复现的问题
title: "[Bug] "
labels: bug
assignees: ''
---

## ⚠️ 先看这里

本项目**不承诺及时响应**（见 [MAINTENANCE.md](../../MAINTENANCE.md)）。
如果你急需修复，建议 fork 后自行修改。

**有一个例外**：如果是 `pytest tests -q` 不是全绿，说明基础功能坏了，会优先看。

---

## 问题描述

<!-- 一句话说清发生了什么 -->

## 复现步骤

```bash
# 1.
# 2.
# 3.
```

## 期望结果

<!-- 你以为会发生什么 -->

## 实际结果

<!-- 实际发生了什么，贴完整报错 -->

```

```

## 环境

| 项 | 值 |
|---|---|
| 操作系统 | <!-- Windows 11 / macOS 14 / Ubuntu 22.04 --> |
| Python 版本 | <!-- python --version --> |
| tznovel 版本 | <!-- tznovel --version --> |
| 安装方式 | <!-- pip install -e . / wheel --> |

## 补充信息

<!-- 如果是抓取问题，请附 tznovel probe 的输出 -->
<!-- 如果是分析问题，请附样本文件的前几行（不要贴整本正文） -->

```
```

## 自查清单

- [ ] 已搜索过现有 Issue，没有重复
- [ ] 用最新代码复现过
- [ ] 贴出的报错信息完整（含 Traceback）
