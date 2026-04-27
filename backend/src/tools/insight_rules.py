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


# 全局规则引擎实例
rule_engine = RuleEngine()
