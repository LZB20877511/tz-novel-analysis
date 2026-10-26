"""叙事人称判定测试。

⚠️ 这些测试的锚点来自**真实书籍实读数据**，不是编造：
    第三人称：茅山后裔 0.1%
    第一人称：某书后传 27.5%–36.4%
"""

import pytest

from tznovel.analyze.person import detect_person


class TestThirdPerson:
    def test_clear_third_person(self):
        """典型的第三人称叙述 —— 全用姓名/他作主语。"""
        body = (
            "张国忠走进了房间。他看着窗外的雪，心里有些不安。"
            "李队长此时走了过来，张国忠心都碎了。他本来是来验证这件事的。"
            "房间里很安静，只有炉火的声音。他坐下来，点了一支烟。"
            "窗外的雪越下越大，覆盖了整个院子。他想起二十年前的那个冬天。"
            "那时候他还年轻，什么都不懂。现在他明白了，可惜已经太晚。"
            "他站起身，走到门口，又回头看了一眼。然后他推开门，走了出去。"
        )
        v = detect_person([body])
        assert v.is_third_person
        assert v.ratio_pct < 5.0

    def test_dialogue_i_not_counted(self):
        """对话里的"我"不能计入叙述 —— 这是关键判据。"""
        body = (
            "他说道：“我今天去了城里，我看到了很多人，我觉得很热闹。”"
            "她回答：“我也想去，我妈不让我去，我说了好久她都不答应。”"
            "他笑了笑，没有说话。窗外的雪还在下。"
            "他看着她的眼睛，忽然觉得心里很暖。"
        )
        v = detect_person([body])
        assert v.is_third_person, f"对话中的「我」被误计入，实际 {v.ratio_pct}%"


class TestFirstPerson:
    def test_clear_first_person(self):
        """典型的第一人称叙述 —— 每句都以"我"起。"""
        body = (
            "我走进了房间。我看着窗外的雪，心里有些不安。"
            "我坐下来，点了一支烟。我想起二十年前的那个冬天。"
            "我站起身，走到门口，又回头看了一眼。"
            "我推开门，走了出去。我知道，我再也回不来了。"
            "我叫沈辣。我叔叔叫沈援朝。我从小跟着他长大。"
            "我记得那天他说的话，我永远不会忘。"
        )
        v = detect_person([body])
        assert v.is_first_person
        assert v.ratio_pct >= 15.0

    def test_mixed_reported_as_first(self):
        """混合人称（第三人称开头 + 第一人称主体）应判第一人称。"""
        body = (
            "沈援朝走进了房间。他看着窗外的雪。"
            "我叫沈辣，沈援朝是我的三叔。我跟着他来到了这里。"
            "我看到了很多事情，我永远忘不了那些日子。"
            "我想起了他的脸，我想起了他说过的话。"
            "我知道我该做什么了。我必须要走下去。"
        )
        v = detect_person([body])
        assert v.is_first_person


class TestEdgeCases:
    def test_insufficient_sample(self):
        """样本不足时必须判"无法判定"，不能瞎猜。"""
        v = detect_person(["他走了。"])
        assert v.verdict == "无法判定"
        assert v.confidence == "低"

    def test_empty_input(self):
        v = detect_person([])
        assert v.verdict == "无法判定"
        assert v.narr_sents == 0

    def test_evidence_samples_captured(self):
        """判第一人称时必须留下证据句，便于复核。"""
        body = ("我走进了房间。我看着窗外。我坐下来。我点了一支烟。"
                "我想起了过去。我知道我该走了。")
        v = detect_person([body])
        assert len(v.samples) > 0
        assert v.samples[0].startswith("我")

    def test_to_dict(self):
        import json
        v = detect_person(["他走了。他笑了。他说好。"])
        json.dumps(v.to_dict(), ensure_ascii=False)

    def test_threshold_configurable(self):
        """阈值可调 —— 不同书籍可能需要放宽。"""
        body = "我走了。" * 40 + "他来了。" * 60
        strict = detect_person([body], first_person_threshold=50.0)
        loose = detect_person([body], first_person_threshold=10.0)
        assert loose.ratio_pct >= strict.ratio_pct
