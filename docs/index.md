# 文档站首页

> 本页由 GitHub Pages 从 `docs/` 自动构建。

## TZ Novel Analysis

**网文阅读分析工具包 —— 读完再说，说必有据。**

一个帮你判断"这本书到底值不值得读"的工具：不是预测你会不会喜欢，而是在你真的读过之后，给你一份**能被别人复核**的评价。

---

## 从这里开始

| 文档 | 内容 |
|---|---|
| [运行环境](ENVIRONMENT.md) | **需要装 WorkBuddy 吗？** 环境要求、常见问题、如何卸载 |
| [方法论](METHODOLOGY.md) | 两条铁律、九条实践规则、双轨评价 |
| [案例分析](CASE-STUDIES.md) | 6 本书的真实分析成果与踩坑记录 |
| [标准流程](data/SOP.md) | 六角色分工、取不到正文时的七级降级链 |
| [评分量表](data/SCORING.md) | 六维权重与质量门槛 |
| [输出模板](data/TEMPLATES.md) | 单书 / 推荐榜 / 对比 三种模板 |

---

## 核心能力

### `tznovel person` —— 叙事人称判定

剔除对话后，统计叙述句中以「我」作主语的比例。阈值 15% 来自实测锚点：

| 书 | 实测占比 | 判定 |
|---|---|---|
| 《茅山后裔》 | 0.1% | 第三人称 |
| 《走进修仙》 | 0.1% | 第三人称 |
| 《民调局异闻录》后传 | 27.5%–36.4% | 第一人称 |

### `tznovel premise` —— 题材前提验证

网上所有题材标签都是人填的，没人验证。实测三次翻车：

- 号称"都市→修仙"的书，现代段仅 **93 字**，在第 1000 字之后
- 号称"第三人称"的书，正文通篇**第一人称**

### `tznovel stats` —— 文风量化

句长 / 段长 / 对话占比 / 标点密度 / 手法词频。廉价转折词分 A、B 两组独立报数 —— 只报 A 组会给人"毫无模板感"的错觉。

---

## 安装

```bash
git clone https://github.com/LZB20877511/tz-novel-analysis.git
cd tz-novel-analysis
pip install -e .
```

或从 [Releases](https://github.com/LZB20877511/tz-novel-analysis/releases) 下载 wheel。

> ⚠️ **本项目尚未发布到 PyPI**，因此不能 `pip install tznovel`。
> 环境要求：Python 3.9+，唯一依赖 `requests`。**不需要 GPU、不需要 API Key。**

---

## 合规边界

| 做 | 不做 |
|---|---|
| 分析**已公开可免费阅读**的章节 | 绕过付费墙 / VIP |
| 抽样阅读（数章） | 批量下载整本并分发 |
| 抓取公开榜单、元数据 | 破解验证码 |
| 本地个人分析 | 二次分发正文 |

**本仓库不包含任何小说正文。**

---

## 维护状态

> ⚠️ **不承诺定期更新、不承诺响应 Issue。**
> 这是个人工具的开源化，不是受支持的产品。如果需要持续维护，**请 fork 自用**。

详见 [MAINTENANCE.md](https://github.com/LZB20877511/tz-novel-analysis/blob/main/MAINTENANCE.md)。

---

**源码仓库**：[github.com/LZB20877511/tz-novel-analysis](https://github.com/LZB20877511/tz-novel-analysis)
