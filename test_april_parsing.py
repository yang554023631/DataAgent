#!/usr/bin/env python3
"""测试"digital_0四月"能不能匹配到"四月" """

from datetime import date, timedelta

text = "广告主 digital_0四月消耗曲线"
text_lower = text.lower()

cn_month_map = {
    '一月': 1, '二月': 2, '三月': 3, '四月': 4,
    '五月': 5, '六月': 6, '七月': 7, '八月': 8,
    '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,
}

for name, num in cn_month_map.items():
    if name in text_lower:
        print(f"✅ 匹配成功: {name} -> 月份 {num}")
        break
else:
    print("❌ 匹配失败")

print(f"\ntext_lower = {repr(text_lower)}")
print(f"'四月' in text_lower = {'四月' in text_lower}")
