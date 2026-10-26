# 贡献指南

感谢你有兴趣改进这个项目。

## 开发环境

```bash
git clone https://github.com/LZB20877511/tz-novel-analysis.git
cd tz-novel-analysis
pip install -e ".[dev]"
pytest tests -q          # 应显示 45 passed
```

## 提交前检查清单

- [ ] `pytest tests -q` 全绿
- [ ] `tznovel --version` 正常
- [ ] 新增功能有对应测试
- [ ] 改了权重常量 → 同步更新 README 与 `tznovel/report/precheck.py`
- [ ] 没有提交任何小说正文、`secrets/` 或抓取产物
- [ ] Python 文件为 **UTF-8 无 BOM**（有 BOM 会导致 `SyntaxError`）

## 特别欢迎的贡献

### 1. 新的书源适配器

放在 `tznovel/fetch/sources/`，继承规则：

```python
from tznovel.fetch.extract import extract_body

def extract_<站点名>(html: str):
    """返回 (正文, 章名) 或 None"""
    ...
```

并在 `sources/__init__.py` 注册。

**注意**：只适配**公开可免费阅读**的页面。

### 2. 词表扩充

三个词表都在 `tznovel/` 下：

| 词表 | 文件 | 用途 |
|---|---|---|
| `MODERN_WORDS` | `analyze/premise.py` | 现代都市强指示词 |
| `CULTIVATION_WORDS` | `analyze/premise.py` | 修真/仙侠强指示词 |
| `SIGNAL_WORDS` / `CHEAP_A` / `CHEAP_B` | `analyze/stats.py` | 手法与转折词 |

**收录原则（重要）**：
- 现代词必须**高辨识度** —— 该词若能在古代/异世界语境自然存在，就**不要收**
  （踩过坑：收了"钱/老师/老板"，导致某书现代词占比虚高到 23.3%，收窄后降到 1.9%）
- 修行词要覆盖常见境界与设定术语

### 3. 判定阈值锚点

如果你用不同题材的书做了实测，发现某个阈值不合适（例如轻小说的人称判定），
欢迎提 Issue 附上**实测数据**：

```
书籍类型：都市轻小说
样本：N 章 / M 字
实测人称占比：X%
当前阈值判定结果：____
你建议改为：____
理由：____
```

**不要只提"阈值可能不对"，要带数据。**

## 代码风格

- 类型注解尽量加（`from __future__ import annotations`）
- 中文注释可以，但要说明**为什么**而不是**是什么**
- 每个模块顶部写清：这个模块解决什么问题、为什么这样设计

## 报告 Bug

请附：

1. 复现命令
2. 期望结果 vs 实际结果
3. Python 版本与操作系统
4. 若涉及抓取：目标 URL 的错误类型（`FATAL` / `IP_BLOCKED` / ...）

## 不要做的事

- ❌ 提交小说正文（仓库不留任何版权内容）
- ❌ 实现验证码绕过或付费墙突破
- ❌ 提交 `secrets/` 或任何令牌
- ❌ 用有 BOM 的 UTF-8 保存 `.py` 文件

## 许可证

提交的代码默认以 [MIT](LICENSE) 授权。
