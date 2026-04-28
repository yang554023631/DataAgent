from typing import Dict, Any, List
from src.tools.insight_rules import rule_engine
from src.tools.insight_llm import generate_natural_language_interpretation, llm_open_scan, aggregate_insights
from src.models.insight import Insight, InsightResult, InsightType
import logging

logger = logging.getLogger(__name__)


async def insight_agent(
    query_result: Dict[str, Any],
    query_context: Dict[str, Any],
    enable_llm_scan: bool = False
) -> InsightResult:
    """
    洞察Agent主入口

    执行流程：
    1. 调用规则引擎执行所有规则，发现问题和亮点
    2. （可选）启用LLM深度扫描，发现未覆盖的洞察
    3. 聚合结果，返回 InsightResult

    Args:
        query_result: 查询结果数据
        query_context: 查询上下文（基准值、配置等）
        enable_llm_scan: 是否启用LLM深度扫描

    Returns:
        InsightResult: 洞察结果对象
    """
    logger.info("开始执行洞察分析...")

    data = query_result.get("data", []) or []
    total_impressions = sum(row.get("impressions", 0) for row in data)

    # 先执行广告主层级规则检查（即使没有数据也要检查，比如欠费/惩罚）
    # 单独调用 P11 和 P12 规则（因为它们不依赖 query_result）
    from src.tools.insight_rules import check_p11_advertiser_punished, check_p12_advertiser_arrears
    advertiser_level_insights = []

    p11 = check_p11_advertiser_punished(query_result, query_context)
    if p11:
        advertiser_level_insights.append(p11)

    p12 = check_p12_advertiser_arrears(query_result, query_context)
    if p12:
        advertiser_level_insights.append(p12)

    # 处理特殊情况：无数据或曝光为0
    no_data = not data or total_impressions == 0
    if no_data and not advertiser_level_insights:
        logger.info("查询结果为空或无曝光数据，返回空洞察")
        result = InsightResult(problems=[], highlights=[], summary="", llm_insights=[])
        result.meta = {"no_data": True}
        return result

    # 1. 调用规则引擎执行其他规则
    rule_insights = []
    if not no_data:
        rule_insights = rule_engine.analyze(query_result, query_context)
        logger.info(f"规则引擎发现 {len(rule_insights)} 个洞察")

    # 合并广告主层级洞察和其他洞察
    all_rule_insights = advertiser_level_insights + rule_insights

    # 2. LLM深度扫描（可选）
    llm_insights: List[Insight] = []
    if enable_llm_scan:
        try:
            llm_insights = llm_open_scan(query_result, query_context)
            logger.info(f"LLM扫描发现额外 {len(llm_insights)} 个洞察")
        except Exception as e:
            logger.error(f"LLM扫描失败: {str(e)}", exc_info=True)

    # 3. 聚合洞察结果
    result = aggregate_insights(all_rule_insights, llm_insights)

    # 4. 生成自然语言解释（更新summary字段）
    all_insights = all_rule_insights + llm_insights
    result.summary = generate_natural_language_interpretation(all_insights, query_result)

    logger.info(f"洞察分析完成: {len(result.problems)}个问题, {len(result.highlights)}个亮点")
    return result


def insights_to_highlights(insight_result: InsightResult) -> List[Dict[str, str]]:
    """
    将 InsightResult 转换为前端 highlights 格式

    转换逻辑：
    - 问题 -> negative 类型 + 🔴图标 + 证据 + 建议
    - 亮点 -> positive 类型 + 🟢图标 + 证据 + 建议
    - 无洞察 -> info 类型 + ⚪平稳提示

    Args:
        insight_result: InsightResult 对象

    Returns:
        List[Dict[str, str]]: 前端 highlights 格式列表，每项包含 type 和 text
    """
    highlights: List[Dict[str, str]] = []

    # 处理无数据情况
    if hasattr(insight_result, 'meta') and insight_result.meta.get('no_data'):
        highlights.append({
            "type": "info",
            "text": "⚪ 暂无数据，请检查查询条件或时间范围"
        })
        return highlights

    # 处理问题（优先级高，先显示）
    for problem in insight_result.problems:
        text_parts = [f"🔴 【{problem.name}】"]
        text_parts.append(f"证据：{problem.evidence}")
        if problem.suggestion:
            text_parts.append(f"建议：{problem.suggestion}")
        highlights.append({
            "type": "negative",
            "text": "｜".join(text_parts)
        })

    # 处理亮点
    for highlight in insight_result.highlights:
        text_parts = [f"🟢 【{highlight.name}】"]
        text_parts.append(f"证据：{highlight.evidence}")
        if highlight.suggestion:
            text_parts.append(f"建议：{highlight.suggestion}")
        highlights.append({
            "type": "positive",
            "text": "｜".join(text_parts)
        })

    # 处理LLM洞察
    for llm_insight in insight_result.llm_insights:
        emoji = "🔴" if llm_insight.type == InsightType.PROBLEM else "🟢" if llm_insight.type == InsightType.HIGHLIGHT else "ℹ️"
        highlights.append({
            "type": llm_insight.type.value,
            "text": f"{emoji} 【{llm_insight.name}】｜证据：{llm_insight.evidence}"
        })

    # 如果没有任何洞察，显示平稳提示
    if not highlights:
        highlights.append({
            "type": "info",
            "text": "⚪ 数据表现平稳，当前未发现显著问题或亮点"
        })

    return highlights
