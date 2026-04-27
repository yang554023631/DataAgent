"""
LLM 洞察层 - 负责将规则洞察转换为自然语言描述，以及 LLM 深度扫描
MVP 版本实现基础接口框架，预留 LLM 扩展空间
"""

from typing import List, Dict, Any, Optional
from src.models.insight import Insight, InsightType, Severity, InsightSource, InsightResult


# ==================== 知识库常量 - 用于后续 LLM Prompt ====================

# 常见问题类型（用于 LLM 问题识别）
PROBLEM_TYPES = {
    "ROI_DECLINE": "ROI 下降",
    "COST_INCREASE": "成本异常上升",
    "CONVERSION_DROP": "转化率大幅下降",
    "REACH_DROP": "触达量大幅下降",
    "FREQUENCY_ABNORMAL": "频次异常",
    "IMPRESSION_DROP": "曝光量大幅下降",
    "CLICK_DROP": "点击量大幅下降",
    "SPEND_WASTE": "预算浪费",
    "DISPARITY": "组间数据差异过大",
}

# 常见优势类型（用于 LLM 亮点识别）
ADVANTAGE_TYPES = {
    "HIGH_ROI": "ROI 表现优异",
    "LOW_COST": "成本控制良好",
    "HIGH_CONVERSION": "转化率表现突出",
    "HIGH_REACH": "触达效果出色",
    "GOOD_FREQUENCY": "频次控制合理",
    "HIGH_IMPRESSION": "曝光量表现突出",
    "HIGH_CLICK": "点击量表现突出",
    "COST_EFFICIENT": "成本效率高",
}


def generate_natural_language_interpretation(
    rule_insights: List[Insight],
    query_data: Dict[str, Any]
) -> str:
    """
    将规则洞察转换为自然语言描述

    MVP 版本：直接基于规则洞察生成结构化描述
    未来扩展：接入 LLM 进行更自然的语言润色和推理

    Args:
        rule_insights: 规则引擎生成的洞察列表
        query_data: 查询数据上下文

    Returns:
        自然语言描述的洞察解释
    """
    if not rule_insights:
        return "未发现显著的数据异常或亮点。"

    # MVP 版本：直接基于洞察类型生成摘要
    problems = [i for i in rule_insights if i.type == InsightType.PROBLEM]
    highlights = [i for i in rule_insights if i.type == InsightType.HIGHLIGHT]

    parts = []

    if problems:
        high_severity = [p for p in problems if p.severity == Severity.HIGH]
        med_severity = [p for p in problems if p.severity == Severity.MEDIUM]

        if high_severity:
            parts.append(f"发现 {len(high_severity)} 个高优先级问题")
        if med_severity:
            parts.append(f"发现 {len(med_severity)} 个中等优先级问题")

    if highlights:
        parts.append(f"发现 {len(highlights)} 个数据亮点")

    if parts:
        return "、".join(parts) + "。"

    return "完成数据分析。"


def llm_open_scan(
    query_data: Dict[str, Any],
    query_context: Optional[Dict[str, Any]] = None
) -> List[Insight]:
    """
    LLM 开放式深度扫描接口

    MVP 版本：返回空列表，预留接口
    未来扩展：让 LLM 自由探索数据，发现规则引擎未覆盖的洞察

    Args:
        query_data: 查询数据
        query_context: 查询上下文（时间范围、维度等）

    Returns:
        LLM 发现的洞察列表
    """
    # MVP 版本：暂不实现，返回空列表
    return []


def aggregate_insights(
    rule_insights: List[Insight],
    llm_insights: List[Insight]
) -> InsightResult:
    """
    聚合规则洞察和 LLM 洞察

    功能：
    1. 按 ID 去重
    2. 按严重程度排序
    3. 分类为 problems 和 highlights
    4. 生成摘要文本

    Args:
        rule_insights: 规则引擎生成的洞察
        llm_insights: LLM 生成的洞察

    Returns:
        聚合后的洞察结果
    """
    # 合并所有洞察
    all_insights = rule_insights + llm_insights

    # 按 ID 去重
    seen_ids = set()
    unique_insights = []
    for insight in all_insights:
        if insight.id not in seen_ids:
            seen_ids.add(insight.id)
            unique_insights.append(insight)

    # 定义严重程度排序权重
    severity_order = {
        Severity.HIGH: 0,
        Severity.MEDIUM: 1,
        Severity.LOW: 2
    }

    # 按严重程度排序（HIGH -> MEDIUM -> LOW）
    sorted_insights = sorted(
        unique_insights,
        key=lambda x: severity_order.get(x.severity, 99)
    )

    # 分类
    problems = [i for i in sorted_insights if i.type == InsightType.PROBLEM]
    highlights = [i for i in sorted_insights if i.type == InsightType.HIGHLIGHT]
    llm_only = [i for i in sorted_insights if i.source == InsightSource.LLM]

    # 生成摘要
    summary_parts = []

    if problems:
        high_count = sum(1 for p in problems if p.severity == Severity.HIGH)
        med_count = sum(1 for p in problems if p.severity == Severity.MEDIUM)
        low_count = sum(1 for p in problems if p.severity == Severity.LOW)

        problem_desc = []
        if high_count:
            problem_desc.append(f"{high_count} 个高优先级")
        if med_count:
            problem_desc.append(f"{med_count} 个中优先级")
        if low_count:
            problem_desc.append(f"{low_count} 个低优先级")

        if problem_desc:
            summary_parts.append(f"发现 {len(problems)} 个问题（{'、'.join(problem_desc)}）")

    if highlights:
        summary_parts.append(f"发现 {len(highlights)} 个数据亮点")

    if summary_parts:
        summary = "；".join(summary_parts) + "。"
    else:
        summary = "未发现显著的数据异常或亮点。"

    return InsightResult(
        problems=problems,
        highlights=highlights,
        summary=summary,
        llm_insights=llm_only
    )
