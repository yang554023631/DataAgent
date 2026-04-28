from typing import Dict, Any, List, Tuple, Optional
from src.tools.time_parser import parse_time_range, TimeRange
from src.tools.term_mapper import map_metrics, map_dimensions
from src.tools.filter_parser import parse_filters
from src.prompts.nlu_prompt import NLU_PROMPT
from src.services.advertiser_service import (
    is_advertiser_list_query,
    extract_advertiser_from_input,
    get_similar_advertiser_names
)


def detect_comparison_query(text: str) -> Tuple[bool, Optional[TimeRange], Optional[TimeRange]]:
    """
    检测是否为对比查询，并尝试解析两个时间范围

    只有当明确包含两个时间周期时，才判断为对比查询，避免误判"细分对比"等

    返回: (is_comparison, time_range1, time_range2)
    """
    # 模式1: "上个月和上上个月"
    if "上个月" in text and "上上个月" in text:
        range1 = parse_time_range.invoke("上个月")
        # 手动计算上上个月
        from datetime import date, timedelta
        today = date.today()
        first_day_of_this_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        last_day_of_two_months_ago = first_day_of_last_month - timedelta(days=1)
        first_day_of_two_months_ago = last_day_of_two_months_ago.replace(day=1)
        range2 = TimeRange(
            start_date=str(first_day_of_two_months_ago),
            end_date=str(last_day_of_two_months_ago),
            unit="day"
        )
        return True, range1, range2

    # 模式2: "今天和昨天"
    if "今天" in text and "昨天" in text:
        range1 = parse_time_range.invoke("今天")
        range2 = parse_time_range.invoke("昨天")
        return True, range1, range2

    # 模式3: "本周 vs 上周"
    if "本周" in text and "上周" in text:
        range1 = parse_time_range.invoke("本周")
        range2 = parse_time_range.invoke("上周")
        return True, range1, range2

    # 模式4: "3月 vs 4月" 或 "3月和4月"
    import re
    month_pattern = r'(\d+月)\s*(vs|VS|和|与)\s*(\d+月)'
    match = re.search(month_pattern, text)
    if match:
        month1 = match.group(1)
        month2 = match.group(3)
        range1 = parse_time_range.invoke(month1)
        range2 = parse_time_range.invoke(month2)
        return True, range1, range2

    # 其他情况：不判断为对比查询，避免误判"细分对比"、"维度对比"等
    return False, None, None

async def nlu_agent(user_input: str, conversation_history: list = None, existing_advertiser_ids: List[str] = None) -> Dict[str, Any]:
    """
    意图理解 Agent（简化版，先用纯规则）

    Args:
        user_input: 用户自然语言输入
        conversation_history: 会话历史

    Returns:
        QueryIntent 结构化数据
    """
    # Step 1: 检测对比查询
    is_comparison, compare_range1, compare_range2 = detect_comparison_query(user_input)

    # Step 2: 先用工具解析可确定的部分
    time_range_result = parse_time_range.invoke(user_input)
    metrics_result = map_metrics.invoke(user_input)
    group_by_result = map_dimensions.invoke(user_input)
    filters_result = parse_filters.invoke(user_input)

    # Step 3: 检测广告主相关意图
    new_advertiser_ids = extract_advertiser_from_input(user_input)
    show_advertiser_list = is_advertiser_list_query(user_input)

    # 广告主 ID 保留逻辑：
    # - 如果新输入提取到了广告主，用新的
    # - 如果没提取到，但之前有，保留之前的
    has_existing_advertiser = existing_advertiser_ids and len(existing_advertiser_ids) > 0
    if new_advertiser_ids:
        advertiser_ids = new_advertiser_ids
    elif has_existing_advertiser:
        advertiser_ids = existing_advertiser_ids
    else:
        advertiser_ids = []

    # 如果没有现有广告主，也没有在新输入中指定，且不是查询列表，标记需要选择广告主
    need_advertiser_selection = not has_existing_advertiser and not advertiser_ids and not show_advertiser_list

    # 检测：用户可能想指定某个广告主，但匹配失败（用于给出名称建议）
    has_ambiguous_advertiser_name = False
    similar_advertisers = []
    if not advertiser_ids and not show_advertiser_list and user_input.strip():
        # 检查是否有类似名称的广告主（用户可能拼写错了或只打了部分）
        similar = get_similar_advertiser_names(user_input)
        # 只要用户有输入且没有匹配到广告主，就标记为 ambiguous（即使没有相似名称）
        has_ambiguous_advertiser_name = True
        similar_advertisers = similar

    # Step 4: 构建结果
    result = {
        "time_range": {
            "start_date": time_range_result.start_date,
            "end_date": time_range_result.end_date,
            "unit": time_range_result.unit
        },
        "metrics": metrics_result,
        "group_by": group_by_result,
        "filters": filters_result,
        "is_incremental": False,
        "intent_type": "comparison" if is_comparison else "query",
        "advertiser_ids": advertiser_ids,
        "show_advertiser_list": show_advertiser_list,
        "need_advertiser_selection": need_advertiser_selection,
        # 对比查询字段
        "is_comparison": is_comparison,
        "compare_time_range": {
            "start_date": compare_range2.start_date,
            "end_date": compare_range2.end_date,
            "unit": compare_range2.unit
        } if is_comparison and compare_range2 else None,
        "ambiguity": {
            "has_ambiguity": has_ambiguous_advertiser_name,
            "type": "advertiser_not_found" if has_ambiguous_advertiser_name else None,
            "reason": "未找到匹配的广告主" if has_ambiguous_advertiser_name else None,
            "options": similar_advertisers
        }
    }

    return result
