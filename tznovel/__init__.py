"""TZ Novel Analysis — 网文阅读分析工具包

核心理念：**读完再说，说必有据。**

与常见的"网文推荐/榜单工具"不同，本项目不做"读之前帮你筛书"，
而是做"**读完之后给出可复核的判断**"：

- 事实层：情节、章数、评分 —— 必须有真实来源，禁止凭记忆编造
- 评价层：文笔、人物、情感 —— 必须给出自己的判断，且必须引原文

两条铁律贯穿全部模块：

1. **事实不许编，评价必须给**
2. **覆盖度不藏**：读了 3 章就说 3 章，不说"通读全书"
"""

__version__ = "1.0.0"
__author__ = "TZ"
__license__ = "MIT"

from tznovel.analyze.stats import analyze_text, StatsResult
from tznovel.analyze.person import detect_person, PersonVerdict
from tznovel.analyze.premise import check_premise, PremiseResult

__all__ = [
    "__version__",
    "analyze_text",
    "StatsResult",
    "detect_person",
    "PersonVerdict",
    "check_premise",
    "PremiseResult",
]
