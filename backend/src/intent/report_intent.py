"""
报表意图识别与填充

流程：
1. LLM 结构化提取（主解析）
2. 规则工具校验（time_parser, map_metrics 等作为交叉验证）
3. 能力校验（指标/层级/维度是否在支持范围内）
4. 必填字段检查（缺了触发澄清）
5. 上下文继承（继承上一轮的广告主/时间/层级）
"""
import json
import logging
from typing import Optional, List, Tuple
from datetime import date

from src.intent.llm_client import get_intent_llm_client, IntentLLMClient
from src.intent.prompts import REPORT_INTENT_SYSTEM_PROMPT
from src.intent.models import ReportIntentResult, ReportTimeRange, ClarificationInfo
from src.intent.capability_registry import (
    validate_metric,
    validate_ad_level,
    validate_dimension,
    get_all_metric_names,
    SUPPORTED_AD_LEVELS,
    AD_LEVEL_MAP,
)

logger = logging.getLogger(__name__)

# 别名澄清阈值（低于此置信度触发别名确认）
ALIAS_CONFIDENCE_THRESHOLD = 0.8

# 必填字段优先级（先问排在前面的）
REQUIRED_FIELDS_PRIORITY = [
    "advertiser_ids",
    "time_range",
    "metrics",
    "ad_level",
]


class ReportIntentAnalyzer:
    """
    报表意图分析器

    用法:
        analyzer = ReportIntentAnalyzer()
        result, clarification = await analyzer.analyze(user_input, existing_advertiser_ids=...)
        if clarification:
            # 需要澄清
        else:
            # 信息齐全，继续流程
    """

    def __init__(self, llm_client: Optional[IntentLLMClient] = None):
        self._llm_client = llm_client

    @property
    def llm_client(self) -> IntentLLMClient:
        if self._llm_client is None:
            self._llm_client = get_intent_llm_client()
        return self._llm_client

    # ---- LLM 提取 ----

    async def _llm_extract(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
    ) -> ReportIntentResult:
        """用 LLM 从用户输入中提取结构化报表意图"""
        today_str = str(date.today())
        system_prompt = REPORT_INTENT_SYSTEM_PROMPT.format(today_date=today_str)

        # 附加上下文
        history_text = ""
        if conversation_history:
            recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = str(msg.get("content", ""))[:200]
                lines.append(f"{role}: {content}")
            history_text = "\n\n对话历史（用于上下文理解）:\n" + "\n".join(lines)

        user_prompt = f"用户输入：{user_input}{history_text}"

        try:
            response_text = await self.llm_client.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True,
            )
            data = json.loads(response_text)

            # 解析 time_range
            tr_data = data.get("time_range")
            time_range = None
            if tr_data and isinstance(tr_data, dict) and tr_data.get("start_date"):
                time_range = ReportTimeRange(
                    start_date=tr_data["start_date"],
                    end_date=tr_data.get("end_date", tr_data["start_date"]),
                    unit=tr_data.get("unit", "day"),
                    is_lifetime=tr_data.get("is_lifetime", False),
                )

            # 解析 compare_time_range
            ctr_data = data.get("compare_time_range")
            compare_time_range = None
            if ctr_data and isinstance(ctr_data, dict) and ctr_data.get("start_date"):
                compare_time_range = ReportTimeRange(
                    start_date=ctr_data["start_date"],
                    end_date=ctr_data.get("end_date", ctr_data["start_date"]),
                    unit=ctr_data.get("unit", "day"),
                    is_lifetime=ctr_data.get("is_lifetime", False),
                )

            result = ReportIntentResult(
                advertiser_ids=data.get("advertiser_ids", []),
                time_range=time_range,
                metrics=data.get("metrics", []),
                ad_level=data.get("ad_level"),
                group_by=data.get("group_by", []),
                filters=data.get("filters", []),
                is_comparison=data.get("is_comparison", False),
                compare_time_range=compare_time_range,
                top_n=data.get("top_n"),
                chart_type=data.get("chart_type"),
                confidence=float(data.get("confidence", 0.7)),
                alias_mappings=data.get("alias_mappings", {}),
            )

            logger.info(
                f"报表意图提取(LLM): 广告主={result.advertiser_ids}, "
                f"时间={result.time_range and result.time_range.start_date + '~' + result.time_range.end_date}, "
                f"指标={result.metrics}, 层级={result.ad_level}, "
                f"置信度={result.confidence:.2f}"
            )
            return result

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(f"报表意图 LLM 提取解析失败: {e}")
            return ReportIntentResult(
                confidence=0.2,
                alias_mappings={},
            )

        except Exception as e:
            logger.error(f"报表意图 LLM 提取调用失败: {e}")
            return ReportIntentResult(
                confidence=0.1,
                alias_mappings={},
            )

    # ---- 规则工具校验（与 LLM 结果交叉验证）----

    def _rule_validate(self, result: ReportIntentResult, user_input: str) -> List[str]:
        """
        用规则工具校验 LLM 提取结果，返回不一致的字段列表

        校验逻辑：
        - 指标：LLM 提取的 vs map_metrics 提取的，取并集
        - 维度：LLM 提取的 vs map_dimensions 提取的，取并集
        - 不一致但置信度高的以 LLM 为准，置信度低的记录警告
        """
        # TODO: 可以在后续优化中引入更复杂的交叉验证
        # 目前只做能力层面的校验（见 check_capabilities）
        inconsistencies = []
        return inconsistencies

    # ---- 能力校验 ----

    def check_capabilities(
        self, result: ReportIntentResult
    ) -> Tuple[bool, Optional[ClarificationInfo]]:
        """
        校验提取结果中的指标/维度/层级是否在系统支持范围内

        Returns:
            (是否全部支持, 不支持时的澄清信息)
        """
        # 校验指标
        unsupported_metrics = []
        validated_metrics = []
        for m in result.metrics:
            ok, std = validate_metric(m)
            if ok:
                validated_metrics.append(std)
            else:
                unsupported_metrics.append(m)

        if unsupported_metrics:
            metric_names = "、".join(unsupported_metrics)
            all_metrics = get_all_metric_names()
            options = [{"value": name, "label": name} for name in all_metrics[:8]]
            return False, ClarificationInfo(
                type="unsupported_metric",
                question=f"抱歉，暂不支持「{metric_names}」指标。\n支持的指标包括：{'、'.join(all_metrics)}\n请选择或输入你想查看的指标：",
                options=options,
                allow_custom_input=True,
                missing_fields=["metrics"],
            )

        # 用校验后的标准指标替换
        result.metrics = validated_metrics

        # 校验广告层级
        if result.ad_level:
            ok, std = validate_ad_level(result.ad_level)
            if not ok:
                options = [
                    {"value": std, "label": names[0] if names else std}
                    for std, names in AD_LEVEL_MAP.items()
                ]
                return False, ClarificationInfo(
                    type="unsupported_metric",  # 复用，实际是层级不支持
                    question=f"抱歉，不支持「{result.ad_level}」广告层级。请选择支持的层级：",
                    options=options,
                    allow_custom_input=False,
                    missing_fields=["ad_level"],
                )
            result.ad_level = std

        # 校验维度
        unsupported_dims = []
        validated_dims = []
        for d in result.group_by:
            ok, std = validate_dimension(d)
            if ok:
                validated_dims.append(std)
            else:
                unsupported_dims.append(d)

        if unsupported_dims:
            dim_names = "、".join(unsupported_dims)
            return False, ClarificationInfo(
                type="unsupported_dimension",
                question=f"抱歉，暂不支持「{dim_names}」维度。请换一个维度试试。",
                options=[],
                allow_custom_input=True,
                missing_fields=["group_by"],
            )

        result.group_by = validated_dims

        return True, None

    # ---- 必填字段检查 ----

    def check_required_fields(
        self, result: ReportIntentResult
    ) -> Tuple[bool, Optional[ClarificationInfo]]:
        """
        检查必填字段是否齐全，缺了生成对应澄清

        按优先级检查，一次只返回第一个缺失项的澄清
        """
        # 1. 广告主
        if not result.advertiser_ids:
            return False, ClarificationInfo(
                type="missing_advertiser",
                question="请问你想查看哪个广告主的数据？请输入广告主名称或 ID。",
                options=[],
                allow_custom_input=True,
                missing_fields=["advertiser_ids"],
            )

        # 2. 时间范围
        if result.time_range is None:
            options = [
                {"value": "今天", "label": "今天"},
                {"value": "昨天", "label": "昨天"},
                {"value": "近7天", "label": "最近 7 天"},
                {"value": "上周", "label": "上周"},
                {"value": "上个月", "label": "上个月"},
                {"value": "近3个月", "label": "最近 3 个月"},
            ]
            return False, ClarificationInfo(
                type="missing_time_range",
                question="请问你想查看哪段时间的数据？",
                options=options,
                allow_custom_input=True,
                missing_fields=["time_range"],
            )

        # 3. 指标
        if not result.metrics:
            all_metrics = get_all_metric_names()
            options = [{"value": name, "label": name} for name in all_metrics[:8]]
            return False, ClarificationInfo(
                type="missing_metrics",
                question="请问你关注哪些指标？",
                options=options,
                allow_custom_input=True,
                missing_fields=["metrics"],
            )

        # 4. 广告层级
        if not result.ad_level:
            options = [
                {"value": "campaign", "label": "计划层级"},
                {"value": "ad_group", "label": "广告组层级"},
                {"value": "creative", "label": "素材/创意层级"},
            ]
            return False, ClarificationInfo(
                type="missing_ad_level",
                question="请问你想看哪个广告层级的数据？",
                options=options,
                allow_custom_input=False,
                missing_fields=["ad_level"],
            )

        return True, None

    # ---- 上下文继承 ----

    def _apply_context_inheritance(
        self,
        result: ReportIntentResult,
        existing_advertiser_ids: List[str] = None,
        existing_time_range: ReportTimeRange = None,
        existing_ad_level: str = None,
    ) -> None:
        """
        继承上下文中的字段（当前轮没提到的，用上一轮的）

        继承策略：广告主、时间范围、广告层级 继承；指标、维度 不继承
        """
        # 广告主
        if not result.advertiser_ids and existing_advertiser_ids:
            result.advertiser_ids = list(existing_advertiser_ids)
            logger.debug(f"继承广告主: {result.advertiser_ids}")

        # 时间范围
        if result.time_range is None and existing_time_range:
            result.time_range = existing_time_range
            logger.debug(f"继承时间范围: {existing_time_range.start_date}~{existing_time_range.end_date}")

        # 广告层级
        if not result.ad_level and existing_ad_level:
            result.ad_level = existing_ad_level
            logger.debug(f"继承广告层级: {existing_ad_level}")

    # ---- 主入口 ----

    async def analyze(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
        existing_advertiser_ids: List[str] = None,
        existing_time_range: ReportTimeRange = None,
        existing_ad_level: str = None,
    ) -> Tuple[Optional[ReportIntentResult], Optional[ClarificationInfo]]:
        """
        分析用户输入，提取报表意图

        Args:
            user_input: 用户输入文本
            conversation_history: 对话历史
            existing_advertiser_ids: 上下文中已有的广告主 ID
            existing_time_range: 上下文中已有的时间范围
            existing_ad_level: 上下文中已有的广告层级

        Returns:
            (意图结果, 澄清信息)
            - 如果信息齐全且能力支持：(result, None)
            - 如果需要澄清：(result, clarification)
            - 如果完全无法解析：(None, clarification)
        """
        # Step 1: LLM 提取
        result = await self._llm_extract(user_input, conversation_history)

        if result.confidence < 0.2:
            # 置信度太低，视为解析失败
            return None, ClarificationInfo(
                type="missing_metrics",  # 先用缺指标的澄清引导用户
                question="抱歉，我没太理解你的需求。请告诉我你想查看哪些数据指标？",
                options=[],
                allow_custom_input=True,
                missing_fields=["metrics"],
            )

        # Step 2: 上下文继承
        self._apply_context_inheritance(
            result, existing_advertiser_ids, existing_time_range, existing_ad_level
        )

        # Step 3: 能力校验
        ok, cap_clarification = self.check_capabilities(result)
        if not ok:
            return result, cap_clarification

        # Step 4: 必填字段检查
        ok, req_clarification = self.check_required_fields(result)
        if not ok:
            return result, req_clarification

        return result, None


# 单例
_report_intent_analyzer: Optional[ReportIntentAnalyzer] = None


def get_report_intent_analyzer() -> ReportIntentAnalyzer:
    """获取报表意图分析器单例"""
    global _report_intent_analyzer
    if _report_intent_analyzer is None:
        _report_intent_analyzer = ReportIntentAnalyzer()
    return _report_intent_analyzer
