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


# ============ 辅助函数 ============

def _get_nested_value(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    """获取嵌套值，支持多个可能的键名"""
    for key in keys:
        if key in row:
            try:
                return float(row[key])
            except (ValueError, TypeError):
                continue
    return None


def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0


# ============ 问题识别规则 ============

def check_p01_audience_mismatch(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P01: 受众定位偏差 - CTR正常但CVR极低"""
    data = query_result.get("data", [])
    ctr_values = [_get_nested_value(row, ["ctr", "CTR", "点击率"]) for row in data]
    cvr_values = [_get_nested_value(row, ["cvr", "CVR", "转化率"]) for row in data]

    avg_ctr = _avg([v for v in ctr_values if v is not None])
    avg_cvr = _avg([v for v in cvr_values if v is not None])

    # CTR在1%-3%区间，但CVR < 0.5%
    if 0.01 <= avg_ctr <= 0.03 and avg_cvr < 0.005:
        return Insight(
            id="P01",
            type=InsightType.PROBLEM,
            name="受众定位偏差",
            severity=Severity.HIGH,
            confidence=0.9,
            source=InsightSource.RULE_ENGINE,
            metric="CTR/CVR",
            current_value=avg_cvr,
            baseline_value=0.005,
            evidence=f"平均点击率 {avg_ctr*100:.1f}% 正常，但平均转化率仅 {avg_cvr*100:.2f}%，低于健康阈值 0.5%",
            suggestion="建议分析转化人群标签与点击人群的差异，可能吸引了非目标用户点击，重新校准定向设置"
        )
    return None


def check_p02_creative_fatigue(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P02: 创意疲劳衰减 - 连续多日CTR下降"""
    data = query_result.get("data", [])
    if len(data) < 3:
        return None

    # 按日期排序的数据
    daily_ctr = []
    for row in data:
        ctr = _get_nested_value(row, ["ctr", "CTR", "点击率"])
        if ctr is not None:
            daily_ctr.append(ctr)

    if len(daily_ctr) >= 3:
        # 检查连续下降趋势
        declining = all(daily_ctr[i] > daily_ctr[i+1] for i in range(min(3, len(daily_ctr)) - 1))
        total_drop = (daily_ctr[0] - daily_ctr[-1]) / daily_ctr[0] if daily_ctr[0] > 0 else 0

        if declining and total_drop > 0.2:
            return Insight(
                id="P02",
                type=InsightType.PROBLEM,
                name="创意疲劳衰减",
                severity=Severity.MEDIUM,
                confidence=0.85,
                source=InsightSource.RULE_ENGINE,
                metric="CTR",
                current_value=daily_ctr[-1],
                baseline_value=daily_ctr[0],
                evidence=f"CTR 连续 {len(daily_ctr)} 天下降，累计降幅 {total_drop*100:.1f}%",
                suggestion="建议准备新的创意素材轮换，当前素材可能已经让目标受众产生审美疲劳"
            )
    return None


def check_p03_time_waste(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P03: 时段投放浪费"""
    data = query_result.get("data", [])
    total_cost = sum(_get_nested_value(row, ["cost", "花费", "消费"]) or 0 for row in data)
    if total_cost == 0:
        return None

    for row in data:
        cost = _get_nested_value(row, ["cost", "花费", "消费"]) or 0
        cost_ratio = cost / total_cost if total_cost > 0 else 0
        cpa = _get_nested_value(row, ["cpa", "CPA", "转化成本"])

        if cost_ratio > 0.3 and cpa is not None:
            # 检查该时段CPA是否是其他时段的2倍
            other_cpas = [
                _get_nested_value(r, ["cpa", "CPA", "转化成本"])
                for r in data if r != row and _get_nested_value(r, ["cpa", "CPA", "转化成本"])
            ]
            if other_cpas and cpa >= 2 * _avg(other_cpas):
                hour = row.get("hour", row.get("时段", "未知"))
                return Insight(
                    id="P03",
                    type=InsightType.PROBLEM,
                    name="时段投放浪费",
                    severity=Severity.HIGH,
                    confidence=0.9,
                    source=InsightSource.RULE_ENGINE,
                    metric="CPA",
                    dimension_value=str(hour),
                    current_value=cpa,
                    baseline_value=_avg(other_cpas),
                    evidence=f"{hour}时段消耗占比 {cost_ratio*100:.1f}%，但CPA达 {cpa:.2f}元，是其他时段的 {cpa/_avg(other_cpas):.1f}倍",
                    suggestion=f"建议降低 {hour} 时段的出价系数或直接屏蔽该低效时段，将预算转移到高转化时段"
                )
    return None


def check_p04_frequency_control(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P04: 频次失控"""
    data = query_result.get("data", [])
    # 检查高频用户消耗占比
    high_freq_cost = 0
    total_cost = 0
    high_freq_conv = 0
    total_conv = 0

    for row in data:
        freq = _get_nested_value(row, ["frequency", "频次", "曝光频次"])
        cost = _get_nested_value(row, ["cost", "花费", "消费"]) or 0
        conv = _get_nested_value(row, ["conversions", "转化", "转化数"]) or 0

        total_cost += cost
        total_conv += conv

        if freq and freq >= 10:
            high_freq_cost += cost
            high_freq_conv += conv

    if total_cost > 0:
        high_freq_cost_ratio = high_freq_cost / total_cost
        high_freq_conv_ratio = high_freq_conv / total_conv if total_conv > 0 else 0

        if high_freq_cost_ratio > 0.3 and high_freq_conv_ratio < 0.05:
            return Insight(
                id="P04",
                type=InsightType.PROBLEM,
                name="频次失控",
                severity=Severity.HIGH,
                confidence=0.9,
                source=InsightSource.RULE_ENGINE,
                metric="frequency",
                current_value=high_freq_cost_ratio,
                baseline_value=0.3,
                evidence=f"曝光10次以上的高频用户消耗了 {high_freq_cost_ratio*100:.1f}% 的预算，但仅贡献了 {high_freq_conv_ratio*100:.1f}% 的转化",
                suggestion="建议设置频次上限（每人每周不超过7次），避免对同一用户过度曝光造成骚扰和浪费"
            )
    return None


def check_p05_fraud_suspicion(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P05: 流量作弊嫌疑"""
    data = query_result.get("data", [])
    avg_ctr = _avg([_get_nested_value(row, ["ctr", "CTR", "点击率"]) for row in data if _get_nested_value(row, ["ctr", "CTR", "点击率"])])

    # 检查异常高的CTR
    if avg_ctr > 0.1:  # >10%
        # 检查跳出率（如果有）
        bounce_rates = [_get_nested_value(row, ["bounce_rate", "跳出率"]) for row in data]
        avg_bounce = _avg([b for b in bounce_rates if b])

        if avg_bounce > 0.9:
            return Insight(
                id="P05",
                type=InsightType.PROBLEM,
                name="流量作弊嫌疑",
                severity=Severity.HIGH,
                confidence=0.95,
                source=InsightSource.RULE_ENGINE,
                metric="CTR/跳出率",
                current_value=avg_ctr,
                evidence=f"CTR异常高达 {avg_ctr*100:.1f}%（行业通常<10%），同时跳出率达 {avg_bounce*100:.1f}%",
                suggestion="高度怀疑遭遇流量作弊，建议检查IP集中度、设备分布、点击时间分布，考虑添加异常流量过滤规则"
            )
    return None


def check_p06_bidding_issue(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P06: 出价策略异常"""
    data = query_result.get("data", [])
    # 检查CPC环比暴涨
    cpc_changes = []
    for row in data:
        cpc_wow = _get_nested_value(row, ["cpc_wow", "cpc_change", "CPC环比"])
        if cpc_wow is not None:
            cpc_changes.append(cpc_wow)

    if any(abs(c) > 1.0 for c in cpc_changes):  # CPC翻倍
        max_change = max(cpc_changes, key=abs)
        return Insight(
            id="P06",
            type=InsightType.PROBLEM,
            name="出价策略异常",
            severity=Severity.MEDIUM,
            confidence=0.8,
            source=InsightSource.RULE_ENGINE,
            metric="CPC",
            current_value=max_change,
            evidence=f"CPC 环比变化达 {max_change*100:+.1f}%，波动异常",
            suggestion="建议检查是否有竞品大幅抬价，或调整出价策略目标，设置最高出价限价避免成本失控"
        )
    return None


def check_p07_saturation(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P07: 地域渗透饱和"""
    data = query_result.get("data", [])
    for row in data:
        region = row.get("region", row.get("地域", row.get("城市", "未知")))
        reach = _get_nested_value(row, ["reach", "覆盖人数", "Reach"])
        cpa = _get_nested_value(row, ["cpa", "CPA", "转化成本"])

        if reach and reach > 0.8 and cpa:  # 覆盖>80%
            # 检查CPA是否显著高于其他地区
            other_cpas = [
                _get_nested_value(r, ["cpa", "CPA", "转化成本"])
                for r in data if r != row and _get_nested_value(r, ["cpa", "CPA", "转化成本"])
            ]
            if other_cpas and cpa >= 1.5 * _avg(other_cpas):
                return Insight(
                    id="P07",
                    type=InsightType.PROBLEM,
                    name="地域渗透饱和",
                    severity=Severity.MEDIUM,
                    confidence=0.85,
                    source=InsightSource.RULE_ENGINE,
                    metric="reach/CPA",
                    dimension_value=str(region),
                    current_value=reach,
                    baseline_value=0.8,
                    evidence=f"{region} 目标人群覆盖率已达 {reach*100:.1f}%，但CPA {cpa:.2f}元是其他地区的 {cpa/_avg(other_cpas):.1f}倍",
                    suggestion=f"{region} 市场已饱和，边际成本上升，建议逐步转移预算到周边低饱和度高潜力城市"
                )
    return None


def check_p08_device_compatibility(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P08: 设备兼容问题"""
    data = query_result.get("data", [])
    device_metrics = {}
    for row in data:
        device = row.get("device", row.get("设备", row.get("os", "未知")))
        ctr = _get_nested_value(row, ["ctr", "CTR", "点击率"])
        cvr = _get_nested_value(row, ["cvr", "CVR", "转化率"])

        if device not in device_metrics:
            device_metrics[device] = {"ctr": [], "cvr": []}
        if ctr is not None:
            device_metrics[device]["ctr"].append(ctr)
        if cvr is not None:
            device_metrics[device]["cvr"].append(cvr)

    # 计算各设备平均表现
    avg_per_device = {}
    for device, metrics in device_metrics.items():
        avg_ctr = _avg(metrics["ctr"]) if metrics["ctr"] else None
        avg_cvr = _avg(metrics["cvr"]) if metrics["cvr"] else None
        if avg_ctr and avg_cvr:
            avg_per_device[device] = {"ctr": avg_ctr, "cvr": avg_cvr}

    if len(avg_per_device) >= 2:
        # 找到最好和最差的设备
        sorted_by_ctr = sorted(avg_per_device.items(), key=lambda x: x[1]["ctr"], reverse=True)
        best_device, best_val = sorted_by_ctr[0]
        worst_device, worst_val = sorted_by_ctr[-1]

        if worst_val["ctr"] <= best_val["ctr"] / 3:
            return Insight(
                id="P08",
                type=InsightType.PROBLEM,
                name="设备兼容问题",
                severity=Severity.MEDIUM,
                confidence=0.8,
                source=InsightSource.RULE_ENGINE,
                metric="CTR",
                dimension_value=worst_device,
                current_value=worst_val["ctr"],
                baseline_value=best_val["ctr"],
                evidence=f"{worst_device} 端CTR仅 {worst_val['ctr']*100:.2f}%，是 {best_device} 端的 {worst_val['ctr']/best_val['ctr']*100:.1f}%",
                suggestion=f"建议检查 {worst_device} 端的广告素材兼容性、落地页加载速度，可能存在技术问题导致用户体验差"
            )
    return None


def check_p09_competitor_impact(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P09: 竞品活动冲击"""
    data = query_result.get("data", [])
    # 检查CPC暴涨同时CTR下降的组合情况
    cpc_spike = False
    ctr_drop = False

    for row in data:
        cpc_wow = _get_nested_value(row, ["cpc_wow", "cpc_change", "CPC环比"])
        ctr_wow = _get_nested_value(row, ["ctr_wow", "ctr_change", "CTR环比"])

        if cpc_wow and cpc_wow > 0.5:  # CPC上涨50%+
            cpc_spike = True
        if ctr_wow and ctr_wow < -0.3:  # CTR下降30%+
            ctr_drop = True

    if cpc_spike and ctr_drop:
        return Insight(
            id="P09",
            type=InsightType.PROBLEM,
            name="竞品活动冲击",
            severity=Severity.MEDIUM,
            confidence=0.75,
            source=InsightSource.RULE_ENGINE,
            metric="CPC/CTR",
            evidence="CPC环比上涨50%以上同时CTR下降30%以上，典型的竞品大促竞价冲击特征",
            suggestion="建议关注竞品动态，可能对方在进行促销活动并加大了投放。可考虑临时提升出价保持竞争力，或避开竞品高峰时段"
        )
    return None


# 问题规则 P01-P09
rule_engine.register(Rule("P01", "受众定位偏差", InsightType.PROBLEM, Severity.HIGH, check_p01_audience_mismatch))
rule_engine.register(Rule("P02", "创意疲劳衰减", InsightType.PROBLEM, Severity.MEDIUM, check_p02_creative_fatigue))
rule_engine.register(Rule("P03", "时段投放浪费", InsightType.PROBLEM, Severity.HIGH, check_p03_time_waste))
rule_engine.register(Rule("P04", "频次失控", InsightType.PROBLEM, Severity.HIGH, check_p04_frequency_control))
rule_engine.register(Rule("P05", "流量作弊嫌疑", InsightType.PROBLEM, Severity.HIGH, check_p05_fraud_suspicion))
rule_engine.register(Rule("P06", "出价策略异常", InsightType.PROBLEM, Severity.MEDIUM, check_p06_bidding_issue))
rule_engine.register(Rule("P07", "地域渗透饱和", InsightType.PROBLEM, Severity.MEDIUM, check_p07_saturation))
rule_engine.register(Rule("P08", "设备兼容问题", InsightType.PROBLEM, Severity.MEDIUM, check_p08_device_compatibility))
rule_engine.register(Rule("P09", "竞品活动冲击", InsightType.PROBLEM, Severity.MEDIUM, check_p09_competitor_impact))
