from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from src.models.insight import Insight, InsightType, Severity, InsightSource
import logging

logger = logging.getLogger(__name__)


@dataclass
class Rule:
    """规则数据类"""
    rule_id: str
    name: str
    type: InsightType
    severity: Severity
    check_fn: Callable[[Dict[str, Any], Dict[str, Any]], Optional[Insight]]


class RuleEngine:
    """规则引擎核心类"""

    def __init__(self):
        self._rules: List[Rule] = []

    def register(self, rule: Rule) -> None:
        """注册规则"""
        self._rules.append(rule)
        logger.info(f"注册规则: {rule.rule_id} - {rule.name}")

    def analyze(self, query_result: Dict[str, Any], query_context: Dict[str, Any]) -> List[Insight]:
        """执行所有规则，返回洞察列表"""
        insights: List[Insight] = []

        for rule in self._rules:
            try:
                insight = rule.check_fn(query_result, query_context)
                if insight:
                    insights.append(insight)
                    logger.info(f"规则 {rule.rule_id} 触发洞察: {insight.name}")
            except Exception as e:
                logger.error(f"规则 {rule.rule_id} 执行失败: {str(e)}", exc_info=True)
                # 单个规则失败不影响整体执行
                continue

        return insights


# 全局规则引擎实例 - 在规则定义前创建
rule_engine = RuleEngine()


# ==================== 亮点规则定义 (A01-A10) ====================


def a01_high_ctr(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A01: CTR表现优异（>基准3倍，默认基准1.5%）"""
    baseline_ctr = query_context.get("baseline_ctr", 0.015)
    threshold = baseline_ctr * 3

    summary = query_result.get("summary", {})
    avg_ctr = summary.get("avg_ctr") or summary.get("ctr", 0)

    if avg_ctr and avg_ctr >= threshold:
        return Insight(
            id="A01",
            type=InsightType.HIGHLIGHT,
            name="CTR表现优异",
            severity=Severity.HIGH,
            confidence=0.95,
            source=InsightSource.RULE_ENGINE,
            metric="ctr",
            current_value=round(avg_ctr * 100, 2),
            baseline_value=round(baseline_ctr * 100, 2),
            evidence=f"当前CTR为{round(avg_ctr * 100, 2)}%，是基准值{round(baseline_ctr * 100, 2)}%的{round(avg_ctr / baseline_ctr, 1)}倍，表现显著优异",
            suggestion="可考虑扩大投放人群或增加预算，利用高CTR获取更多曝光",
            metadata={"benchmark": baseline_ctr, "threshold": threshold}
        )
    return None


def a02_high_cvr(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A02: CVR表现优异（>基准3倍，默认基准3%）"""
    baseline_cvr = query_context.get("baseline_cvr", 0.03)
    threshold = baseline_cvr * 3

    summary = query_result.get("summary", {})
    avg_cvr = summary.get("avg_cvr") or summary.get("cvr", 0)

    if avg_cvr and avg_cvr >= threshold:
        return Insight(
            id="A02",
            type=InsightType.HIGHLIGHT,
            name="CVR表现优异",
            severity=Severity.HIGH,
            confidence=0.95,
            source=InsightSource.RULE_ENGINE,
            metric="cvr",
            current_value=round(avg_cvr * 100, 2),
            baseline_value=round(baseline_cvr * 100, 2),
            evidence=f"当前CVR为{round(avg_cvr * 100, 2)}%，是基准值{round(baseline_cvr * 100, 2)}%的{round(avg_cvr / baseline_cvr, 1)}倍，转化效率极高",
            suggestion="这是优质转化人群，建议加大投放力度并优化落地页",
            metadata={"benchmark": baseline_cvr, "threshold": threshold}
        )
    return None


def a03_low_cpc(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A03: CPC成本优势（<均价50%，默认基准2元）"""
    baseline_cpc = query_context.get("baseline_cpc", 2.0)
    threshold = baseline_cpc * 0.5

    summary = query_result.get("summary", {})
    avg_cpc = summary.get("avg_cpc") or summary.get("cpc", 0)

    if avg_cpc and avg_cpc <= threshold:
        return Insight(
            id="A03",
            type=InsightType.HIGHLIGHT,
            name="CPC成本优势显著",
            severity=Severity.HIGH,
            confidence=0.9,
            source=InsightSource.RULE_ENGINE,
            metric="cpc",
            current_value=round(avg_cpc, 2),
            baseline_value=round(baseline_cpc, 2),
            evidence=f"当前CPC为{round(avg_cpc, 2)}元，仅为基准值{round(baseline_cpc, 2)}元的{round(avg_cpc / baseline_cpc * 100, 0)}%，成本优势明显",
            suggestion="低价流量窗口，建议增加投放预算抢占流量",
            metadata={"benchmark": baseline_cpc, "threshold": threshold}
        )
    return None


def a04_healthy_spend_curve(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A04: 消耗曲线健康（预算利用率>90%，变异系数<0.2）"""
    summary = query_result.get("summary", {})
    budget_util = summary.get("budget_utilization", 0)
    cv = summary.get("spend_cv", 0)  # 变异系数

    if budget_util >= 0.9 and cv < 0.2:
        return Insight(
            id="A04",
            type=InsightType.HIGHLIGHT,
            name="消耗曲线健康",
            severity=Severity.MEDIUM,
            confidence=0.85,
            source=InsightSource.RULE_ENGINE,
            metric="spend",
            current_value=round(budget_util * 100, 1),
            baseline_value=90,
            evidence=f"预算利用率达到{round(budget_util * 100, 1)}%，消耗曲线变异系数{round(cv, 3)}，投放节奏平稳",
            suggestion="当前投放节奏良好，可保持现有策略",
            metadata={"budget_util": budget_util, "cv": cv}
        )
    return None


def a05_good_frequency_control(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A05: 频次控制良好（平均频次1.5-2.5）"""
    summary = query_result.get("summary", {})
    avg_freq = summary.get("avg_frequency", summary.get("frequency", 0))

    if 1.5 <= avg_freq <= 2.5:
        return Insight(
            id="A05",
            type=InsightType.HIGHLIGHT,
            name="曝光频次控制良好",
            severity=Severity.MEDIUM,
            confidence=0.8,
            source=InsightSource.RULE_ENGINE,
            metric="frequency",
            current_value=round(avg_freq, 2),
            baseline_value=2.0,
            evidence=f"平均曝光频次为{round(avg_freq, 2)}次，处于1.5-2.5次的理想区间",
            suggestion="频次控制合理，既保证有效触达又避免过度曝光",
            metadata={"min_target": 1.5, "max_target": 2.5}
        )
    return None


def a06_ideal_conversion_timing(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A06: 转化节奏理想（24h转化占比>80%）"""
    summary = query_result.get("summary", {})
    conversion_24h_ratio = summary.get("conversion_24h_ratio", 0)

    if conversion_24h_ratio > 0.8:
        return Insight(
            id="A06",
            type=InsightType.HIGHLIGHT,
            name="转化节奏理想",
            severity=Severity.MEDIUM,
            confidence=0.85,
            source=InsightSource.RULE_ENGINE,
            metric="conversion_timing",
            current_value=round(conversion_24h_ratio * 100, 1),
            baseline_value=80,
            evidence=f"24小时内完成转化占比{round(conversion_24h_ratio * 100, 1)}%，转化决策周期短",
            suggestion="用户决策链路短，可优化广告投放时段匹配转化高峰",
            metadata={"conversion_24h_ratio": conversion_24h_ratio}
        )
    return None


def a07_time_slot_cvr_contrast(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A07: 分时段反差亮点（某时段CVR>整体3倍）"""
    summary = query_result.get("summary", {})
    overall_cvr = summary.get("avg_cvr") or summary.get("cvr", 0)

    if overall_cvr <= 0:
        return None

    breakdowns = query_result.get("breakdowns", {})
    time_slots = breakdowns.get("time_slot", [])

    for slot in time_slots:
        slot_cvr = slot.get("cvr", 0)
        if slot_cvr >= overall_cvr * 3:
            return Insight(
                id="A07",
                type=InsightType.HIGHLIGHT,
                name="分时段CVR反差亮点",
                severity=Severity.HIGH,
                confidence=0.9,
                source=InsightSource.RULE_ENGINE,
                metric="cvr",
                dimension_key="time_slot",
                dimension_value=slot.get("name", ""),
                current_value=round(slot_cvr * 100, 2),
                baseline_value=round(overall_cvr * 100, 2),
                evidence=f"{slot.get('name', '')}时段CVR达{round(slot_cvr * 100, 2)}%，是整体均值的{round(slot_cvr / overall_cvr, 1)}倍",
                suggestion=f"重点投放{slot.get('name', '')}时段，可显著提升整体转化效率",
                metadata={"overall_cvr": overall_cvr, "slot_cvr": slot_cvr}
            )
    return None


def a08_device_roi_contrast(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A08: 分设备反差亮点（某设备ROI>其他2倍）"""
    breakdowns = query_result.get("breakdowns", {})
    devices = breakdowns.get("device", [])

    if len(devices) < 2:
        return None

    device_rois = [(d.get("roi", 0), d.get("name", "")) for d in devices if d.get("roi", 0) > 0]
    if len(device_rois) < 2:
        return None

    device_rois.sort(reverse=True)
    highest_roi, highest_device = device_rois[0]
    second_roi, _ = device_rois[1]

    if highest_roi >= second_roi * 2:
        return Insight(
            id="A08",
            type=InsightType.HIGHLIGHT,
            name="分设备ROI反差亮点",
            severity=Severity.HIGH,
            confidence=0.9,
            source=InsightSource.RULE_ENGINE,
            metric="roi",
            dimension_key="device",
            dimension_value=highest_device,
            current_value=round(highest_roi, 2),
            baseline_value=round(second_roi, 2),
            evidence=f"{highest_device}设备ROI达{round(highest_roi, 2)}，是次优设备的{round(highest_roi / second_roi, 1)}倍",
            suggestion=f"向{highest_device}设备倾斜预算，可获得更高回报",
            metadata={"highest_roi": highest_roi, "second_roi": second_roi, "device": highest_device}
        )
    return None


def a09_material_ctr_cvr_contrast(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A09: 分素材反差亮点（低CTR<1%但高CVR>5%）"""
    breakdowns = query_result.get("breakdowns", {})
    materials = breakdowns.get("material", [])

    for mat in materials:
        ctr = mat.get("ctr", 0)
        cvr = mat.get("cvr", 0)
        if ctr < 0.01 and cvr > 0.05:
            return Insight(
                id="A09",
                type=InsightType.HIGHLIGHT,
                name="素材反差亮点-精准定向型",
                severity=Severity.HIGH,
                confidence=0.85,
                source=InsightSource.RULE_ENGINE,
                metric="mixed",
                dimension_key="material",
                dimension_value=mat.get("name", ""),
                current_value=round(cvr * 100, 2),
                baseline_value=5.0,
                evidence=f"素材「{mat.get('name', '')}」CTR仅{round(ctr * 100, 2)}%但CVR高达{round(cvr * 100, 2)}%，属于高质量精准流量",
                suggestion="该素材转化质量高，可优化素材封面提升点击率同时保持高转化",
                metadata={"ctr": ctr, "cvr": cvr, "material": mat.get("name", "")}
            )
    return None


def a10_high_impression_share(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A10: 展示份额优势（展示份额>60%）"""
    summary = query_result.get("summary", {})
    impression_share = summary.get("impression_share", 0)

    if impression_share > 0.6:
        return Insight(
            id="A10",
            type=InsightType.HIGHLIGHT,
            name="展示份额优势明显",
            severity=Severity.MEDIUM,
            confidence=0.8,
            source=InsightSource.RULE_ENGINE,
            metric="impression_share",
            current_value=round(impression_share * 100, 1),
            baseline_value=60,
            evidence=f"当前展示份额达{round(impression_share * 100, 1)}%，在竞争中占据主导地位",
            suggestion="市场话语权强，可优化出价策略维持份额同时提升利润率",
            metadata={"impression_share": impression_share}
        )
    return None


# ==================== 规则注册 ====================

# 亮点规则 A01-A10
rule_engine.register(Rule("A01", "CTR表现优异", InsightType.HIGHLIGHT, Severity.HIGH, a01_high_ctr))
rule_engine.register(Rule("A02", "CVR表现优异", InsightType.HIGHLIGHT, Severity.HIGH, a02_high_cvr))
rule_engine.register(Rule("A03", "CPC成本优势", InsightType.HIGHLIGHT, Severity.HIGH, a03_low_cpc))
rule_engine.register(Rule("A04", "消耗曲线健康", InsightType.HIGHLIGHT, Severity.MEDIUM, a04_healthy_spend_curve))
rule_engine.register(Rule("A05", "频次控制良好", InsightType.HIGHLIGHT, Severity.MEDIUM, a05_good_frequency_control))
rule_engine.register(Rule("A06", "转化节奏理想", InsightType.HIGHLIGHT, Severity.MEDIUM, a06_ideal_conversion_timing))
rule_engine.register(Rule("A07", "分时段反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, a07_time_slot_cvr_contrast))
rule_engine.register(Rule("A08", "分设备反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, a08_device_roi_contrast))
rule_engine.register(Rule("A09", "分素材反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, a09_material_ctr_cvr_contrast))
rule_engine.register(Rule("A10", "展示份额优势", InsightType.HIGHLIGHT, Severity.MEDIUM, a10_high_impression_share))
