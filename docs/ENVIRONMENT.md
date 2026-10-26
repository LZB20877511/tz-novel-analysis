# 运行环境与 Agent 协作模型

> 这一节回答一个容易被忽略的问题：**这套东西到底在什么环境下用？**

本项目有两层，可以分开用，也可以一起用：

| 层 | 是什么 | 依赖 |
|---|---|---|
| **① Python 工具包**（`tznovel`） | 文风量化、人称判定、题材验证、报告自检 | 只需 Python 3.9+，**任何环境都能跑** |
| **② Agent 协作模型**（`agents/` + `docs/SOP.md`） | 多角色分工完成一次完整的书籍分析 | 需要支持多 Agent 协作的宿主环境 |

**大多数人只需要第 ① 层。** 第 ② 层是这套方法的"原始形态"，适合想让 AI 完整跑一遍分析流程的人。

---

## 一、Python 工具包（推荐起点）

### 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| **Python** | **3.9 / 3.10 / 3.11 / 3.12** | CI 在三个系统 × 四个版本上验证过 |
| **操作系统** | Windows / macOS / Linux 均可 | 无平台特定代码 |
| **依赖** | 仅 `requests` | 没有 Pandas / NumPy / 浏览器驱动等重依赖 |
| **网络** | 只有 `tznovel fetch` 需要 | 纯分析功能**完全离线** |
| **内存** | 无特殊要求 | 分析 20 章量级文本，百 MB 级足够 |
| **磁盘** | < 1 MB（不含抓取产物） | — |

### 安装

```bash
pip install tznovel          # 若已发布到 PyPI
# 或从源码
pip install -e ".[dev]"
```

### 验证

```bash
tznovel --version            # tznovel 1.0.0
pytest tests -q              # 45 passed
```

### 不需要什么（重要）

- ❌ **不需要 GPU**
- ❌ **不需要任何大模型 API Key** —— 所有分析都是**确定性算法**，没有一次网络推理调用
- ❌ **不需要浏览器/Playwright** —— 抓取层是纯 HTTP
- ❌ **不需要数据库**

> **这是刻意的设计**：分析结论必须**可复现**。
> 同一个输入，任何人跑都得到同一个数字 —— 否则"证据"就失去意义。

---

## 二、Agent 协作模型（第 ② 层）

### 设计假设

这套流程假设宿主环境具备：

1. **多 Agent 并行** —— 能同时启动多个独立上下文的子 Agent
2. **文件读写** —— Agent 之间通过**落盘文件**交换产出（不靠对话上下文传递）
3. **网页访问** —— 部分角色需要抓取页面

> **核心设计：Agent 之间不直接对话，全部通过文件交接。**
> 因为对话上下文会丢失细节，而文件是可复查的。每一份产出都留在 `reports/` 下，随时能回看。

### 六个角色的分工

| 角色 | 职责 | 关键约束 |
|---|---|---|
| **book-scout** 书目定位官 | 消歧、元数据、章节结构、正文可读性 | **不接受"大概"** —— 字数/章数/状态必须来自页面实测 |
| **chapter-reader** 章节速读官 | 真实读正文，产出摘要卡 | **禁止编造情节**；必须报 `pua` / `latin` / `U+FFFD` 三项污染指标 |
| **review-miner** 评论取证官 | 采集外部口碑 | **只采别人的话，不做自己的判断**；必须正反两面都取 |
| **model-critic** 独立评论员 | 基于正文给出六维自评 | **先自评、后对照**，顺序不能颠倒 |
| **spoiler-guard** 防剧透审校 | 语义级剧透审查 | **未过闸门禁止发布** |
| **genre-hunter** 寻书猎手 | 无书名模式下海选候选 | 必须给落选记录与理由 |

### 一次完整分析的数据流

```
用户给出书名
   │
   ├─ book-scout ──────────► 元数据 + 三区间章节 URL
   │
   ├─ chapter-reader ×N ───► 摘要卡（并行，区间不重叠）
   ├─ review-miner ────────► 外部共识
   │
   ├─ model-critic ────────► 六维自评（先不看外部评论）
   │        └─ 再对照 ─────► 分歧说明（≥1.5 分必须单列）
   │
   ├─ 程序闸门 ────────────► tznovel check（6 项自检）
   ├─ spoiler-guard ───────► 语义审校
   │
   └─ 汇总输出 ────────────► reports/<书名>_分析_<日期>.md
```

### 如果宿主不支持多 Agent 怎么办

**完全可以单线程跑。** 按上表顺序，充当每个角色、把产出写进对应文件即可。

多 Agent 的价值只是**并行提速**与**避免自评被外部评论污染**（让两个角色在不同上下文里工作）。单线程跑时，只要**先写自评、再读外部评论**，效果是一样的。

---

## 三、这套方法的价值不依赖任何特定工具

即使你完全不用本仓库的代码，以下四条规则本身就成立：

1. **事实不许编，评价必须给** —— 情节要有来源，评价要有自己的判断
2. **覆盖度不藏** —— 读了 3 章就说 3 章
3. **双轨评价，分歧不抹平** —— 自评与外部共识并列，差 ≥1.5 分单列
4. **剧透是硬闸门** —— 结局、反转、配对不出现在简介里

详见 [`METHODOLOGY.md`](METHODOLOGY.md)。

---

## 四、常见环境问题

<details>
<summary><b>Windows 上 .ps1 脚本报中文乱码 / 语法错误</b></summary>

PowerShell 5.1 会把**无 BOM 的 UTF-8** 当 GBK 读，导致中文正则损坏。
保存 `.ps1` 时用 UTF-8 **带 BOM**：

```powershell
[System.IO.File]::WriteAllText($path, $content,
  (New-Object System.Text.UTF8Encoding($true)))
```

反过来，**Python 的 `.py` 文件必须无 BOM**，否则 `SyntaxError: invalid non-printable character U+FEFF`。
</details>

<details>
<summary><b>pip install 后命令找不到</b></summary>

确认虚拟环境的 `Scripts/`（Windows）或 `bin/`（Unix）在 PATH 中。
或者直接用模块方式调用：

```bash
python -m tznovel.cli --version
```
</details>

<details>
<summary><b>抓取一直 403</b></summary>

先跑 `tznovel probe <url>` 看错误类型：

- `IP_BLOCKED` → 换 UA（工具会自动降级到移动端 UA）或换 IP
- `EMPTY_SITE` → **站点自身没内容，换源，别硬刚**
- `FATAL` → 页面不存在

**实测最常见的误判**：以为 403 就需要浏览器自动化。实际上很多站是
**WAF 按 UA 判定**（PC UA 403 / 移动 UA 200），换 UA 就过。
</details>

<details>
<summary><b>中文 Windows 终端输出乱码</b></summary>

```powershell
$env:PYTHONIOENCODING = "utf-8"
```
</details>

---

## 五、本项目的开发环境（如实说明）

这套方法是在 Windows + PowerShell 上，配合支持多 Agent 协作的宿主逐步打磨出来的，
六本书的实测数据都来自那个环境。

**但代码本身没有平台绑定** —— CI 在 Ubuntu / Windows / macOS 上均通过 45 个测试。
