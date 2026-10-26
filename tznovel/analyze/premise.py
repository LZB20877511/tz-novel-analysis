"""题材前提验证。

问题背景：网上所有"题材标签"都是人工填的，没人验证。实测三次翻车：

    《走进修仙》号称"都市→修仙" → 实读：现代段仅 93 字，在第 1000 字之后，实为开局即仙侠
    《民调局异闻录》号称"第三人称" → 实读：正文通篇第一人称（"我叫沈辣"）
    《修真聊天群》号称"有跃迁"     → 实读：都市与修真界并存，不离开都市

本模块把"题材前提"变成可量化校验：现代词 vs 修行词的分布与密度。

⚠️ 词表必须"高辨识度"：只收仙侠/古代绝不会出现的现代专有物。
   实测教训：初版收了「钱/块/元/老师/老板」等通用词，
   导致《走进修仙》被误判成"现代词占 23.3%"。收窄后降到 1.9%，与实读吻合。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from tznovel.analyze.stats import clean_paragraphs

# ---------- 词表（高辨识度，古代/异世界绝不会出现） ----------

MODERN_WORDS: tuple[str, ...] = (
    # 电子/通讯
    "手机", "电话", "电脑", "微信", "网络", "互联网", "短信", "视频",
    "电视", "摄像机", "耳机", "充电", "信号", "卫星", "U盘", "硬盘",
    # 现代机构/制度
    "公安局", "派出所", "警车", "局长", "书记", "市政府", "省政府",
    "公务员", "身份证", "户口本", "银行卡", "档案", "职称", "编制",
    "大学", "高中", "初中", "教室", "班主任", "教务处", "辅导员",
    # 交通/城市设施
    "地铁", "公交", "出租车", "高铁", "航班", "驾照", "红绿灯",
    "电梯", "写字楼", "小区", "物业", "公寓楼", "停车位", "超市", "便利店",
    # 现代消费品
    "外卖", "快递", "奶茶", "可乐", "咖啡", "啤酒", "香烟", "泡面",
    "方便面", "网吧", "酒吧", "电影院", "火锅店",
    # 现代医疗
    "医院", "急诊", "输液", "抗生素", "手术室", "病历",
)

CULTIVATION_WORDS: tuple[str, ...] = (
    "修仙", "修真", "修炼", "功法", "灵气", "真元", "丹药", "灵石", "法宝",
    "筑基", "金丹", "元婴", "化神", "炼气", "渡劫", "飞升", "仙尊", "仙帝",
    "宗门", "掌门", "长老", "师兄", "师姐", "拜师", "弟子", "剑修", "道侣",
    "法术", "术法", "神通", "符箓", "法阵", "洞府", "妖兽", "灵根", "境界",
    "秘境", "天劫", "元神", "神魂", "剑气", "飞剑", "储物袋", "纳戒",
)

OTHERWORLD_WORDS: tuple[str, ...] = (
    "穿越", "异界", "重生", "前世", "穿越者", "异世界",
    "地球", "轮回", "投胎", "穿越到",
)


@dataclass
class ChapterScene:
    """单章场景统计。"""

    label: str = ""
    title: str = ""
    chars: int = 0
    modern: int = 0
    cultivation: int = 0
    otherworld: int = 0
    modern_per_k: float = 0.0
    cultivation_per_k: float = 0.0


@dataclass
class PremiseResult:
    """题材前提验证结果。"""

    chapters: list[ChapterScene] = field(default_factory=list)
    total_chars: int = 0
    modern_total: int = 0
    cultivation_total: int = 0
    otherworld_total: int = 0
    modern_share_pct: float = 0.0
    modern_per_k: float = 0.0
    cultivation_per_k: float = 0.0
    first_modern_pos: int = -1
    first_cultivation_pos: int = -1
    first_otherworld_pos: int = -1
    transition: str = "样本不足"
    transition_detail: str = ""

    @property
    def has_urban_segment(self) -> bool:
        """现代词占比 ≥10% 视为存在都市段。"""
        return self.modern_share_pct >= 10.0

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["chapters"] = [c.__dict__ for c in self.chapters]
        d["has_urban_segment"] = self.has_urban_segment
        return d


def _count(text: str, words: Iterable[str]) -> int:
    return sum(text.count(w) for w in words)


def _first_pos(text: str, words: Iterable[str]) -> int:
    positions = [text.find(w) for w in words if w in text]
    return min(positions) if positions else -1


def check_premise(
    chapters: Iterable[dict],
    *,
    body_key: str = "body",
    label_key: str = "label",
    title_key: str = "title",
    urban_share_threshold: float = 10.0,
    drop_ratio_threshold: float = 0.4,
) -> PremiseResult:
    """校验"都市/修行"题材前提。

    Args:
        chapters: [{"label":..,"title":..,"body":..}]
        urban_share_threshold: 现代词占比低于该值 → 判"无都市段"
        drop_ratio_threshold: 后半现代词密度 < 前半 × 该值 → 判"有跃迁"

    Returns:
        PremiseResult
    """
    per: list[ChapterScene] = []
    texts: list[str] = []

    for i, ch in enumerate(chapters):
        body = ch.get(body_key, "") if isinstance(ch, dict) else str(ch)
        paras = clean_paragraphs(body or "")
        if not paras:
            continue
        text = "".join(paras)
        n = len(text)
        if n == 0:
            continue
        m = _count(text, MODERN_WORDS)
        c = _count(text, CULTIVATION_WORDS)
        o = _count(text, OTHERWORLD_WORDS)
        per.append(ChapterScene(
            label=str(ch.get(label_key, i + 1)) if isinstance(ch, dict) else str(i + 1),
            title=str(ch.get(title_key, ""))[:20] if isinstance(ch, dict) else "",
            chars=n, modern=m, cultivation=c, otherworld=o,
            modern_per_k=round(1000 * m / n, 2),
            cultivation_per_k=round(1000 * c / n, 2),
        ))
        texts.append(text)

    if not per:
        return PremiseResult()

    all_text = "".join(texts)
    total = len(all_text)
    mt = _count(all_text, MODERN_WORDS)
    ct = _count(all_text, CULTIVATION_WORDS)
    ot = _count(all_text, OTHERWORLD_WORDS)
    share = 100.0 * mt / (mt + ct) if (mt + ct) else 0.0

    # 跃迁判定：现代词密度是否随章节显著下降
    transition, detail = "样本不足（需≥4章）", ""
    if len(per) >= 4:
        half = len(per) // 2
        e_chars = sum(c.chars for c in per[:half]) or 1
        l_chars = sum(c.chars for c in per[half:]) or 1
        e = 1000 * sum(c.modern for c in per[:half]) / e_chars
        l = 1000 * sum(c.modern for c in per[half:]) / l_chars
        if share < urban_share_threshold:
            transition = "无都市段（修行词占绝对优势）"
            detail = f"现代词仅占 {share:.1f}%"
        elif e > 0 and l < e * drop_ratio_threshold:
            transition = "有跃迁（现代词密度显著下降）"
            detail = f"前半 {e:.2f}/千字 → 后半 {l:.2f}/千字"
        else:
            transition = "都市与修行并存（未退出都市）"
            detail = f"现代词密度 前半 {e:.2f} → 后半 {l:.2f}（未显著下降）"

    return PremiseResult(
        chapters=per,
        total_chars=total,
        modern_total=mt,
        cultivation_total=ct,
        otherworld_total=ot,
        modern_share_pct=round(share, 1),
        modern_per_k=round(1000 * mt / total, 2) if total else 0.0,
        cultivation_per_k=round(1000 * ct / total, 2) if total else 0.0,
        first_modern_pos=_first_pos(all_text, MODERN_WORDS),
        first_cultivation_pos=_first_pos(all_text, CULTIVATION_WORDS),
        first_otherworld_pos=_first_pos(all_text, OTHERWORLD_WORDS),
        transition=transition,
        transition_detail=detail,
    )
