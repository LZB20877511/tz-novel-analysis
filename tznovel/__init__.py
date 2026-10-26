"""TZ Novel Analysis 鈥?缃戞枃闃呰鍒嗘瀽宸ュ叿鍖?
鏍稿績鐞嗗康锛?*璇诲畬鍐嶈锛岃蹇呮湁鎹€?*

涓庡父瑙佺殑"缃戞枃鎺ㄨ崘/姒滃崟宸ュ叿"涓嶅悓锛屾湰椤圭洰涓嶅仛"璇讳箣鍓嶅府浣犵瓫涔?锛?鑰屾槸鍋?**璇诲畬涔嬪悗缁欏嚭鍙鏍哥殑鍒ゆ柇**"锛?
- 浜嬪疄灞傦細鎯呰妭銆佺珷鏁般€佽瘎鍒?鈥斺€?蹇呴』鏈夌湡瀹炴潵婧愶紝绂佹鍑蹇嗙紪閫?- 璇勪环灞傦細鏂囩瑪銆佷汉鐗┿€佹儏鎰?鈥斺€?蹇呴』缁欏嚭鑷繁鐨勫垽鏂紝涓斿繀椤诲紩鍘熸枃

涓ゆ潯閾佸緥璐┛鍏ㄩ儴妯″潡锛?
1. **浜嬪疄涓嶈缂栵紝璇勪环蹇呴』缁?*
2. **瑕嗙洊搴︿笉钘?*锛氳浜?3 绔犲氨璇?3 绔狅紝涓嶈"閫氳鍏ㄤ功"
"""

__version__ = "1.0.1"
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
