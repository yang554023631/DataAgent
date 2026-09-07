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
from src.services.advertiser_service import (
    get_all_advertisers,
    get_advertiser_by_id,
)
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
    # ad_level 不再是必填，默认使用 campaign
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
                schema=ReportIntentResult,
            )
            data = json.loads(response_text)

            # 解析 time_range
            tr_data = data.get("time_range")
            time_range = None
            if tr_data and isinstance(tr_data, dict):
                # 对于全生命周期，start_date 和 end_date 是空字符串
                # 所以只需要检查 tr_data 存在，不需要检查 start_date 非空
                time_range = ReportTimeRange(
                    start_date=tr_data.get("start_date", ""),
                    end_date=tr_data.get("end_date", ""),
                    unit=tr_data.get("unit", "day"),
                    is_lifetime=tr_data.get("is_lifetime", False),
                )

            # 解析 compare_time_range
            ctr_data = data.get("compare_time_range")
            compare_time_range = None
            if ctr_data and isinstance(ctr_data, dict):
                compare_time_range = ReportTimeRange(
                    start_date=ctr_data.get("start_date", ""),
                    end_date=ctr_data.get("end_date", ""),
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
                sort=data.get("sort"),
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

    async def _rule_validate(self, result: ReportIntentResult, user_input: str) -> List[str]:
        """
        用规则工具校验 LLM 提取结果，返回不一致的字段列表

        校验逻辑：
        - 指标：LLM 提取的 vs map_metrics 提取的，取并集
        - 维度：LLM 提取的 vs map_dimensions 提取的，取并集
        - 不一致但置信度高的以 LLM 为准，置信度低的记录警告
        - 如果 LLM 提取失败（advertiser_ids 为空），尝试规则提取广告主 ID
        """
        from src.tools.term_mapper import map_metrics as mapped_tool
        from src.tools.term_mapper import map_dimensions
        # Reuse the same regex logic from intent_analyzer to extract advertiser ids
        import re

        # Get the underlying function from StructuredTool
        rule_map_metrics = mapped_tool.func
        rule_map_dimensions = map_dimensions.func

        # 规则提取指标
        rule_metrics = rule_map_metrics(user_input)
        # Merge: take union of LLM metrics and rule metrics
        if rule_metrics:
            combined = list(set(result.metrics + rule_metrics))
            result.metrics = combined
            logger.info(f"Rule metrics merged: LLM had {len(result.metrics)}, rule added {len(rule_metrics)}, combined {len(combined)}")

        # 规则提取维度
        rule_dims = rule_map_dimensions(user_input)
        # Merge: take union of LLM dimensions and rule dimensions
        if rule_dims:
            combined = list(set(result.group_by + rule_dims))
            result.group_by = combined
            logger.info(f"Rule dimensions merged: LLM had {len(result.group_by)}, rule added {len(rule_dims)}, combined {len(combined)}")

        # 规则提取广告主 IDs (if LLM failed to extract any)
        if not result.advertiser_ids:
            # Extract using the same regex patterns as intent_analyzer
            ADVERTISER_ID_PATTERNS = [
                r'id[为是]\s*([a-f0-9\-]+)\s*的?广告主',
                r'广告主id[为是]\s*([a-f0-9\-]+)',
                r'广告主id\s*[为是]?\s*([a-f0-9\-]+)',
                r'广告主\s*[：:]\s*([a-f0-9\-]+)',
                r'advertiser\s*[=:]\s*([a-f0-9\-]+)',
                r'([a-f0-9\-]{8,}-[a-f0-9\-]+)\s*广告主',
                r'广告主\s*([a-f0-9\-]{8,})',
                r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
                r'id[为是]\s*(\d+)\s*的?广告主',
                r'广告主id[为是]\s*(\d+)',
                r'广告主id\s*[为是]?\s*(\d+)',
                r'广告主\s*[：:]\s*(\d+)',
                r'advertiser\s*[=:]\s*(\d+)',
                r'(\d+)\s*号广告主',
                r'(\d+)\s*广告主',
                r'广告主\s*(\d+)',
            ]
            ids = []
            text_lower = user_input.lower()
            for pattern in ADVERTISER_ID_PATTERNS:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                for match in matches:
                    adv_id_str = str(match).strip()
                    try:
                        adv_id_int = int(adv_id_str)
                        if str(adv_id_int) not in ids:
                            ids.append(str(adv_id_int))
                    except ValueError:
                        if adv_id_str not in ids:
                            ids.append(adv_id_str)
            if ids:
                result.advertiser_ids = ids
                logger.info(f"Rule advertiser_ids extracted: {ids}")

        # 如果advertiser_ids里有内容，但看起来不像ID（不是纯数字/UUID），尝试通过名称搜索转换为ID
        from src.services.advertiser_service import extract_advertiser_from_input

        # 1. 如果advertiser_ids为空，从输入中搜索
        if not result.advertiser_ids:
            matched_ids = await extract_advertiser_from_input(user_input)
            if matched_ids:
                result.advertiser_ids = matched_ids
                logger.info(f"Name search extracted advertiser_ids: {matched_ids}")
        else:
            # 2. 检查advertiser_ids是否都是有效的ID格式，如果有无效的尝试重新搜索
            all_valid = True
            for adv_id in result.advertiser_ids:
                # 如果不是纯数字，说明可能是名称，需要重新搜索
                if not adv_id.isdigit():
                    all_valid = False
                    break
            if not all_valid:
                matched_ids = await extract_advertiser_from_input(user_input)
                if matched_ids:
                    result.advertiser_ids = matched_ids
                    logger.info(f"Name search replaced advertiser_ids: {matched_ids}")

        # 规则提取时间范围 (if LLM failed to extract)
        if not result.time_range:
            from src.analysis.intent_analyzer import simple_parse_time_range
            parsed = simple_parse_time_range(user_input)
            if parsed:
                from src.intent.models import ReportTimeRange
                result.time_range = ReportTimeRange(
                    start_date=parsed.start_date,
                    end_date=parsed.end_date,
                    unit=parsed.unit,
                )
                logger.info(f"Rule time_range extracted: {parsed.start_date} to {parsed.end_date}")

        # 规则提取广告层级 - 如果文本中明确提到某个层级，覆盖LLM结果
        # 顺序：长模式先匹配，短模式后匹配（避免"广告主"先匹配了"广告计划"中的"广告"）
        AD_LEVEL_PATTERNS = [
            (r'广告\s*计划', 'campaign'),
            (r'广告\s*组', 'ad_group'),
            (r'广告\s*主', 'advertiser'),
            (r'计划', 'campaign'),
            (r'组', 'ad_group'),
            (r'整个', 'advertiser'),
            (r'全部', 'advertiser'),
            (r'创意', 'creative'),
            (r'素材', 'creative'),
        ]
        text_lower = user_input.lower()
        for pattern, level in AD_LEVEL_PATTERNS:
            if re.search(pattern, text_lower):
                if result.ad_level != level:
                    result.ad_level = level
                    logger.info(f"Rule ad_level extracted: {level} (overwriting LLM result)")
                break

        # 对提取到的advertiser_names搜索转换为ID
        if result.advertiser_names:
            from src.services.advertiser_service import get_advertiser_by_name
            for name in result.advertiser_names:
                matched_advertisers = await get_advertiser_by_name(name)
                for adv in matched_advertisers:
                    adv_id = adv["id"]
                    if adv_id not in result.advertiser_ids:
                        result.advertiser_ids.append(adv_id)
            logger.info(f"[名称→ID] 输入名称: {result.advertiser_names}, 输出IDs: {result.advertiser_ids}")

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
        # If user didn't specify time range, DEFAULT to full lifetime (don't ask clarification)
        if result.time_range is None:
            from src.intent.models import ReportTimeRange
            # Default to full lifetime query with empty start/end and is_lifetime=True
            result.time_range = ReportTimeRange(
                start_date="",
                end_date="",
                unit="day",
                is_lifetime=True,
            )
            logger.info("No time_range specified, default to full lifetime (is_lifetime=True)")

        # 如果是全生命周期，不需要 start_date 和 end_date，跳过检查
        if result.time_range.is_lifetime:
            # is_lifetime = true 表示查询全生命周期，不需要补充时间
            pass
        elif not (result.time_range.start_date and result.time_range.end_date):
            # 不是全生命周期，但起止时间不全，需要澄清
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

        # 4. 广告层级（不再必填，默认使用 campaign）
        if not result.ad_level:
            logger.info("ad_level 未指定，默认使用 campaign")
            result.ad_level = "campaign"

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

        # 时间范围（兼容 dict 和 ReportTimeRange 对象两种格式）
        if result.time_range is None and existing_time_range:
            # 如果是 dict（经序列化后从 state 恢复），转为对象
            if isinstance(existing_time_range, dict):
                existing_time_range = ReportTimeRange(
                    start_date=existing_time_range.get("start_date", ""),
                    end_date=existing_time_range.get("end_date", existing_time_range.get("start_date", "")),
                    unit=existing_time_range.get("unit", "day"),
                    is_lifetime=existing_time_range.get("is_lifetime", False),
                )
            result.time_range = existing_time_range
            logger.debug(f"继承时间范围: {existing_time_range.start_date}~{existing_time_range.end_date}")

        # 广告层级
        if not result.ad_level and existing_ad_level:
            result.ad_level = existing_ad_level
            logger.debug(f"继承广告层级: {existing_ad_level}")

    async def _build_advertiser_lookup_report(self, result: ReportIntentResult) -> Optional[dict]:
        """
        基于 LLM 结构化提取结果，判断是否为纯广告主查询并生成 final_report。

        判断逻辑（完全基于 LLM 输出，不做关键词规则匹配）：
        - 没有指标（metrics 为空）
        - 没有维度（group_by 为空）
        - 没有时间范围（time_range 为空）
        - ad_level 为空或为 advertiser（不是 campaign/ad_group/creative 等报表层级）

        满足以上条件 → 判定为纯广告主信息查询：
        - 有 advertiser_ids → 返回单个/多个广告主详情
        - 没有 advertiser_ids → 返回广告主列表
        """
        # 懒加载避免循环导入
        from src.graph.nodes import _generate_suggested_queries

        has_metrics = bool(result.metrics)
        has_group_by = bool(result.group_by)
        has_time_range = result.time_range is not None
        is_report_level = result.ad_level in ("campaign", "ad_group", "creative", "ad")

        # 只要有任何报表特征（指标/维度/时间/报表层级），就不是纯广告主查询
        if has_metrics or has_group_by or has_time_range or is_report_level:
            return None

        # 纯广告主查询
        advertiser_ids = result.advertiser_ids

        if advertiser_ids:
            # 有具体广告主 ID → 返回广告主详情
            import asyncio
            advertisers = await asyncio.gather(*[get_advertiser_by_id(aid) for aid in advertiser_ids])
            advertisers = [a for a in advertisers if a]

            if not advertisers:
                return {
                    "title": "未找到广告主",
                    "time_range": {"start": "", "end": ""},
                    "metrics": [],
                    "highlights": [
                        {"type": "warning", "text": f"⚠️ 未找到ID为 {advertiser_ids} 的广告主"}
                    ],
                    "data_table": {"columns": [], "rows": []},
                    "next_queries": ["有哪些广告主"],
                }

            if len(advertisers) == 1:
                adv = advertisers[0]
                return {
                    "title": f"广告主 {adv['id']} 信息",
                    "time_range": {"start": "", "end": ""},
                    "metrics": [],
                    "highlights": [
                        {"type": "info", "text": f"广告主ID: `{adv['id']}`"},
                        {"type": "info", "text": f"广告主名称: **{adv['name']}**"},
                    ],
                    "data_table": {"columns": [], "rows": []},
                    "next_queries": _generate_suggested_queries(adv['name']),
                }
            else:
                highlights = [
                    {"type": "info", "text": f"找到 {len(advertisers)} 个广告主:"}
                ]
                for adv in advertisers:
                    highlights.append(
                        {"type": "info", "text": f"• ID: `{adv['id']}` 名称: **{adv['name']}**"}
                    )
                return {
                    "title": "广告主信息",
                    "time_range": {"start": "", "end": ""},
                    "metrics": [],
                    "highlights": highlights,
                    "data_table": {
                        "columns": ["广告主ID", "广告主名称"],
                        "rows": [[adv["id"], adv["name"]] for adv in advertisers]
                    },
                    "next_queries": _generate_suggested_queries(advertisers[0]['name']),
                }
        else:
            # 没有具体广告主 → 返回广告主列表
            advertisers = await get_all_advertisers()
            if not advertisers:
                return {
                    "title": "暂无可用广告主",
                    "time_range": {"start": "", "end": ""},
                    "metrics": [],
                    "highlights": [{"type": "info", "text": "⚠️ 当前没有查询到任何可用广告主"}],
                    "data_table": {"columns": ["广告主ID", "广告主名称"], "rows": []},
                    "next_queries": [],
                }

            return {
                "title": "可用广告主列表",
                "time_range": {"start": "", "end": ""},
                "metrics": [],
                "highlights": [
                    {"type": "info", "text": "💡 点击以下广告主名称即可查看对应数据"}
                ],
                "data_table": {
                    "columns": ["广告主ID", "广告主名称"],
                    "rows": [[adv["id"], adv["name"]] for adv in advertisers]
                },
                "next_queries": _generate_suggested_queries(advertisers[0]['name']) if advertisers else [],
            }



    # ---- 路由判断 ----

    def _determine_query_route(self, result: ReportIntentResult, user_input: str) -> Tuple[str, str, str]:
        """
        判断查询路由

        v1.3.0 之后所有报表查询统一走 CoT analysis_node，
        旧的 structured / nl_dsl 路径保留但不再作为默认路由。

        Returns:
            (route: str, reason: str, analysis_type: str)
            route: "analysis" （CoT 分析节点）
            analysis_type: 从 result 中推断的分析类型
        """
        # 推断分析类型（供 analysis_node 参考，实际以 CotPlanner 判断为准）
        analysis_type = "time_trend" if result.group_by and "date" in result.group_by else "standard_report"

        return "analysis", "v1.3 CoT 分析引擎", analysis_type

    # ---- 主入口 ----

    async def analyze(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
        existing_advertiser_ids: List[str] = None,
        existing_time_range: ReportTimeRange = None,
        existing_ad_level: str = None,
    ) -> Tuple[Optional[ReportIntentResult], Optional[ClarificationInfo], Optional[dict], dict]:
        """
        分析用户输入，提取报表意图

        Args:
            user_input: 用户输入文本
            conversation_history: 对话历史
            existing_advertiser_ids: 上下文中已有的广告主 ID
            existing_time_range: 上下文中已有的时间范围
            existing_ad_level: 上下文中已有的广告层级

        Returns:
            (意图结果, 澄清信息, final_report, route_info)
            route_info: dict with keys:
                - route: "structured" / "nl_dsl" / "advertiser_lookup" / "pending_clarification"
                - reason: str describing why this route was chosen
                - analysis_type: "standard_report" / "exploratory_query" / "qa" / ""
            - 如果是纯广告主查询：(None, None, final_report, route_info)
            - 如果信息齐全：(result, None, None, route_info)
            - 如果需要澄清：(result, clarification, None, route_info)
            - 如果完全无法解析：(None, clarification, None, route_info)
        """
        # Step 1: LLM 提取
        result = await self._llm_extract(user_input, conversation_history)

        # Step 2: 上下文继承
        self._apply_context_inheritance(
            result, existing_advertiser_ids, existing_time_range, existing_ad_level
        )

        # Step 2.5: 基于规则的交叉验证和合并（必须在能力校验之前）
        # 使用规则提取作为补充，LLM 漏提的指标/维度通过规则提取补充
        # 即使 LLM 置信度低，也先用规则补充，看是否能凑齐必填字段
        await self._rule_validate(result, user_input)

        if result.confidence < 0.2:
            # 置信度太低，但先检查规则提取是否已经凑齐必填字段
            # 如果已经凑齐，继续流程，不要直接返回澄清
            ok, _ = self.check_required_fields(result)
            if ok:
                # 规则已经凑齐，继续流程
                pass
            else:
                # 仍然缺字段，返回澄清
                route_info = {"route": "pending_clarification", "reason": "需要澄清后再路由", "analysis_type": ""}
                return None, ClarificationInfo(
                    type="missing_metrics",  # 先用缺指标的澄清引导用户
                    question="抱歉，我没太理解你的需求。请告诉我你想查看哪些数据指标？",
                    options=[],
                    allow_custom_input=True,
                    missing_fields=["metrics"],
                ), None, route_info

        # Step 3: 基于 LLM 结构化结果判断是否为纯广告主查询
        # （完全基于 LLM 输出的结构化字段，不依赖关键词规则）
        final_report = await self._build_advertiser_lookup_report(result)
        if final_report is not None:
            logger.info(f"报表意图识别: 判定为纯广告主查询（基于LLM结构化结果），直接返回结果")
            route_info = {"route": "advertiser_lookup", "reason": "纯广告主查询", "analysis_type": "qa"}
            return None, None, final_report, route_info

        # Step 4: 能力校验，失败时返回澄清（后续可调整为路由 nl_dsl）
        ok, cap_clarification = self.check_capabilities(result)
        if not ok:
            route_info = {"route": "pending_clarification", "reason": "需要澄清后再路由", "analysis_type": ""}
            return result, cap_clarification, None, route_info

        # Step 5: 必填字段检查
        ok, req_clarification = self.check_required_fields(result)
        if not ok:
            route_info = {"route": "pending_clarification", "reason": "需要澄清后再路由", "analysis_type": ""}
            return result, req_clarification, None, route_info

        # Step 6: 路由判断
        route, reason, analysis_type = self._determine_query_route(result, user_input)
        route_info = {
            "route": route,
            "reason": reason,
            "analysis_type": analysis_type
        }
        logger.info(f"报表意图路由判断: 路径={route}, 原因={reason}, 分析类型={analysis_type}")

        return result, None, None, route_info


# 单例
_report_intent_analyzer: Optional[ReportIntentAnalyzer] = None


def get_report_intent_analyzer() -> ReportIntentAnalyzer:
    """获取报表意图分析器单例"""
    global _report_intent_analyzer
    if _report_intent_analyzer is None:
        _report_intent_analyzer = ReportIntentAnalyzer()
    return _report_intent_analyzer
