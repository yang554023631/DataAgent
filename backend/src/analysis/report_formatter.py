"""ReportFormatter - 报告包装器

将分析结果包装成统一的报告格式，返回给前端。
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.analysis.models import (
    AnalysisPlan,
    AnalysisType,
    ChartType,
    CotReasoning,
    AnalysisPlanResult,
)
from src.nl_dsl.models import (
    FilterResult,
    QualityResult,
    QualityIssue,
    QualityCheckType,
    QualityAction,
    AnalysisResult as NlDslAnalysisResult,
    EmptyCheckResult,
)
from src.tools.hierarchy_utils import get_entity_names
from src.analysis.chart_validator import validate_chart_report

logger = logging.getLogger(__name__)


class ReportFormatter:
    """报告包装器"""

    @classmethod
    def format(
        cls,
        analysis_plan_result: AnalysisPlanResult = None,
        analysis_result: NlDslAnalysisResult = None,
        quality_result: QualityResult = None,
        filter_result: FilterResult = None,
        user_input: str = None,
        cot_reasoning: Optional[CotReasoning] = None,
        # Backward compatibility parameters
        analysis_plan: AnalysisPlan = None,
        chart_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """格式化分析结果为最终报告

        Args:
            analysis_plan_result: 分析计划结果（包含分析计划和筛选计划）
            analysis_result: 分析执行结果
            quality_result: 质量检查结果
            filter_result: 筛选结果
            user_input: 用户原始输入
            cot_reasoning: CoT 推理过程（可选）

        Returns:
            最终报告字典
        """
        # Backward compatibility
        if analysis_plan is None and analysis_plan_result is not None:
            analysis_plan = analysis_plan_result.analysis_plan
        if chart_data is None and analysis_result is not None:
            chart_data = analysis_result.chart_data or {}
        if chart_data is None:
            chart_data = {}
        if quality_result is None:
            quality_result = QualityResult(passed=True)
        if filter_result is None:
            filter_result = FilterResult(entity_ids=[], entity_level="advertiser", total_count=0)

        # 1. 判断报告类型
        report_type = cls._determine_report_type(quality_result, chart_data)

        if report_type == "error":
            return cls.format_error(
                error_type="data_empty",
                message="未找到有效的分析结果",
                reason="数据为空或质量检查失败",
                suggestions=["调整筛选条件", "扩大时间范围", "检查指标是否正确"],
                recommended_queries=["查看最近7天的整体数据", "查看全部广告主数据"]
            )

        # 2. 生成标题
        title = cls._generate_title_from_plan(analysis_plan, filter_result)
        if report_type == "hitl":
            title = f"⚠️ 需要人工介入 - {title}"

        # 3. 提取图表配置和数据
        # If analysis_result directly contains chart_config (returned from AnalysisExecutor.execute), use it
        chart_config = None
        if analysis_result is not None and hasattr(analysis_result, 'chart_config') and analysis_result.chart_config is not None:
            if hasattr(analysis_result.chart_config, 'model_dump'):
                chart_config = analysis_result.chart_config.model_dump()
            else:
                chart_config = analysis_result.chart_config
        # Fallback: extract from chart_data if needed
        if chart_config is None:
            chart_config = chart_data.get("chart_config", {})
        data = chart_data.get("data", [])

        # 更新 chart_config.title 确保和当前指标一致
        if analysis_plan and len(analysis_plan.metrics) > 0 and "type" in chart_config:
            primary_metric = analysis_plan.metrics[0]
            metric_display = cls._get_metric_display_name(primary_metric)
            chart_type = chart_config.get("type")
            if chart_type == "line":
                chart_config["title"] = f"{metric_display} 趋势"
            elif chart_type == "bar":
                if analysis_plan.analysis_type == "period_comparison":
                    chart_config["title"] = f"{metric_display} 对比"
                else:
                    chart_config["title"] = f"{metric_display} 分布"
            elif chart_type == "pie":
                chart_config["title"] = f"{metric_display} 分布"

        # 对 date 字段进行格式化（如果是时间戳）
        start_date = analysis_plan.time_range.start_date if analysis_plan and analysis_plan.time_range else None
        end_date = analysis_plan.time_range.end_date if analysis_plan and analysis_plan.time_range else None
        if data and len(data) > 0 and start_date and end_date:
            # 检查第一个点是否有 date 字段且是数字（时间戳）
            first_point = data[0]
            if "date" in first_point and isinstance(first_point["date"], (int, float)):
                # 格式化所有点的 date
                for point in data:
                    if "date" in point and isinstance(point["date"], (int, float)):
                        point["date"] = cls._format_date_timestamp(int(point["date"]), start_date, end_date)

        # 4. 格式化数据表格
        if analysis_result is not None and analysis_result.data_table is not None:
            data_table = cls._format_analysis_data_table(analysis_result.data_table, analysis_plan.metrics, analysis_plan)
        else:
            data_table = cls._format_data_table(chart_data.get("data", []), analysis_plan.metrics if analysis_plan else [], analysis_plan)

        # 5. 生成亮点
        highlights = cls._generate_highlights(
            data=data,
            metrics=analysis_plan.metrics,
            quality_result=quality_result,
            data_table=data_table
        )

        # 6. 准备质量信息
        quality_info = cls._format_quality_info(quality_result)

        # 7. 准备元数据
        # Convert pydantic object to dict if needed for metadata generation
        if analysis_plan is not None and filter_result is not None:
            chart_config_dict = chart_config
            if hasattr(chart_config, 'model_dump'):
                chart_config_dict = chart_config.model_dump()
            elif not isinstance(chart_config, dict):
                chart_config_dict = {}
            metadata = cls._generate_metadata(filter_result, analysis_plan, chart_config_dict)
        else:
            metadata = {}

        # 8. CoT 推理摘要
        if cot_reasoning is None and analysis_plan_result is not None:
            cot_reasoning = analysis_plan_result.reasoning
        cot_reasoning_summary = cls._summarize_cot_reasoning(cot_reasoning)

        # 9. 生成推荐查询
        if analysis_plan is not None:
            next_queries = cls._generate_next_queries(analysis_plan, data)
        else:
            next_queries = []

        # Build final report
        report_dict = {
            "report_type": report_type,
            "title": title,
            "chart_config": chart_config,
            "data": data,
            "data_table": data_table,
            "quality_info": quality_info,
            "highlights": highlights,
            "metadata": metadata,
            "cot_reasoning_summary": cot_reasoning_summary,
            "next_queries": next_queries
        }

        # Validate chart data structure before returning
        validation = validate_chart_report(report_dict)
        if not validation.is_valid:
            error_msgs = "; ".join(validation.errors)
            logger.error(f"Chart data validation failed: {error_msgs}")
            return cls.format_error(
                error_type="validation_error",
                message="图表数据结构校验失败",
                reason=error_msgs,
                suggestions=["请重试查询", "检查查询条件"],
                recommended_queries=[user_input] if user_input else []
            )

        return report_dict

    @classmethod
    def format_empty_result(
        cls,
        empty_check_result: EmptyCheckResult,
        analysis_plan_result: AnalysisPlanResult,
        filter_result: FilterResult,
        user_input: str,
    ) -> Dict[str, Any]:
        """格式化空结果报告

        Args:
            empty_check_result: 空检查结果
            analysis_plan_result: 分析计划结果
            filter_result: 筛选结果
            user_input: 用户原始输入

        Returns:
            最终报告字典
        """
        # 构建建议列表
        suggestions = empty_check_result.hints or [
            "调整筛选条件",
            "扩大时间范围",
            "检查指标是否正确"
        ]

        # 生成标题
        title = cls._generate_title_from_plan(analysis_plan_result.analysis_plan, filter_result)

        return {
            "report_type": "empty",
            "title": f"📭 {title}",
            "highlights": [
                {
                    "type": "negative",
                    "text": f"⚠️ {empty_check_result.hints[0] if empty_check_result.hints else '未找到符合条件的数据'}"
                }
            ],
            "data_table": {"columns": [], "rows": []},
            "chart_config": None,
            "metadata": cls._generate_metadata(filter_result, analysis_plan_result.analysis_plan, {}),
            "next_queries": ["查看最近7天的整体数据", "查看全部广告主"],
            "suggestions": suggestions
        }

    @classmethod
    def format_error(
        cls,
        error_type: str,
        message: str,
        reason: str,
        suggestions: List[str],
        recommended_queries: List[str]
    ) -> Dict[str, Any]:
        """格式化错误报告

        Args:
            error_type: 错误类型 query_failed / intent_unclear / data_empty / system_error
            message: 用户友好的错误消息
            reason: 具体原因
            suggestions: 解决建议列表
            recommended_queries: 推荐查询列表

        Returns:
            错误报告字典
        """
        return {
            "report_type": "error",
            "error_type": error_type,
            "message": message,
            "reason": reason,
            "suggestions": suggestions,
            "recommended_queries": recommended_queries
        }

    @classmethod
    def _determine_report_type(
        cls,
        quality_result: QualityResult,
        chart_data: Dict[str, Any]
    ) -> str:
        """判断报告类型"""
        # 检查是否需要人工介入
        for issue in quality_result.issues:
            if issue.severity == "hitl_required" or issue.suggested_action == QualityAction.HITL:
                return "hitl"

        # 检查是否有数据
        data = chart_data.get("data", [])
        if not data and quality_result.passed is False:
            return "error"

        return "success"

    @classmethod
    def _generate_title_from_plan(cls, analysis_plan: AnalysisPlan, filter_result: FilterResult = None) -> str:
        """从分析计划生成标题"""
        analysis_type_names = {
            AnalysisType.ENTITY_TABLE: "实体表格",
            AnalysisType.TIME_TREND: "趋势",
            AnalysisType.PERIOD_COMPARISON: "对比分析",
            AnalysisType.AUDIENCE_DISTRIBUTION: "受众分布",
            AnalysisType.SUMMARY: "数据汇总",
        }

        type_name = analysis_type_names.get(analysis_plan.analysis_type, "数据分析")
        metrics = analysis_plan.metrics

        # 主标题构建：优先用第一个指标名称 + 类型
        if metrics and len(metrics) > 0:
            primary_metric = metrics[0]
            metric_display = cls._get_metric_display_name(primary_metric)
            title_base = f"{metric_display} {type_name}"
        else:
            title_base = type_name

        # 如果只筛选了一个实体，添加实体信息前缀
        if filter_result and filter_result.total_count == 1:
            entity_level = filter_result.entity_level
            # 实体级别显示名称
            level_display = {
                "advertiser": "广告主",
                "campaign": "广告计划",
                "adgroup": "广告组",
                "creative": "创意",
            }.get(entity_level, entity_level)
            # 取第一个 entity_id
            entity_ids = filter_result.entity_ids
            if entity_ids and len(entity_ids) == 1:
                entity_id = entity_ids[0]
                title_base = f"{level_display}ID={entity_id} {title_base}"

        time_range = analysis_plan.time_range
        start_date = time_range.start_date
        end_date = time_range.end_date

        if start_date and end_date:
            return f"{title_base} ({start_date} ~ {end_date})"
        return title_base

    @classmethod
    def _format_data_table(cls, data: List[Dict[str, Any]], metrics: List[str], analysis_plan: AnalysisPlan = None) -> Dict[str, Any]:
        """格式化数据表格（从字典列表）"""
        if not data:
            return {"columns": [], "rows": []}

        # 获取所有列名
        columns = list(data[0].keys())

        # 格式化行数据
        rows = []
        for row in data:
            formatted_row = []
            for col in columns:
                value = row.get(col)
                # 格式化日期字段（如果是时间戳）
                col_lower = col.lower()
                if (col_lower.find("date") != -1 or col_lower.find("time") != -1 or
                    col_lower.find("day") != -1 or col_lower.find("hour") != -1):
                    if isinstance(value, (int, float)) and analysis_plan and analysis_plan.time_range:
                        start_date = analysis_plan.time_range.start_date
                        end_date = analysis_plan.time_range.end_date
                        if start_date and end_date:
                            value = cls._format_date_timestamp(int(value), start_date, end_date)
                # 格式化百分比字段
                elif col in metrics and (col_lower.find("ctr") != -1 or col_lower.find("cvr") != -1):
                    if isinstance(value, (int, float)):
                        value = f"{value * 100:.1f}%"
                # 格式化金额字段
                elif col in metrics and (col_lower.find("cost") != -1 or col_lower.find("spend") != -1):
                    if isinstance(value, (int, float)):
                        value = f"¥{value:,.2f}"
                # 格式化数字字段
                elif col in metrics and isinstance(value, (int, float)):
                    value = f"{value:,}"
                formatted_row.append(value)
            rows.append(formatted_row)

        return {
            "columns": columns,
            "rows": rows
        }

    @classmethod
    def _format_analysis_data_table(cls, data_table, metrics: List[str], analysis_plan: AnalysisPlan = None) -> Dict[str, Any]:
        """格式化数据表格（从 AnalysisDataTable 对象）"""
        if not data_table:
            return {"columns": [], "rows": []}

        # 如果是字典格式
        if isinstance(data_table, dict):
            columns = data_table.get("columns", [])
            rows = data_table.get("rows", [])
        # 如果是对象格式
        else:
            columns = getattr(data_table, "columns", [])
            rows = getattr(data_table, "rows", [])

        # 格式化行数据
        formatted_rows = []
        for row in rows:
            # 如果行是字典，提取值并格式化
            if isinstance(row, dict):
                formatted_row = []
                # 遍历原始 columns，每个 column 保留 key 用于取值，只在取值后用 label 显示
                for col in columns:
                    # 如果列是字典，获取 key 用于取值
                    col_key = col.get("key", col) if isinstance(col, dict) else col
                    value = row.get(col_key)
                    # 格式化日期字段（如果是时间戳）
                    col_key_lower = str(col_key).lower()
                    if (col_key_lower.find("date") != -1 or col_key_lower.find("time") != -1 or
                        col_key_lower.find("day") != -1 or col_key_lower.find("hour") != -1):
                        if isinstance(value, (int, float)) and analysis_plan and analysis_plan.time_range:
                            start_date = analysis_plan.time_range.start_date
                            end_date = analysis_plan.time_range.end_date
                            if start_date and end_date:
                                value = cls._format_date_timestamp(int(value), start_date, end_date)
                    # 格式化百分比字段
                    elif col_key in metrics and (col_key_lower.find("ctr") != -1 or col_key_lower.find("cvr") != -1):
                        if isinstance(value, (int, float)):
                            value = f"{value * 100:.1f}%"
                    # 格式化金额字段
                    elif col_key in metrics and (col_key_lower.find("cost") != -1 or col_key_lower.find("spend") != -1):
                        if isinstance(value, (int, float)):
                            value = f"¥{value:,.2f}"
                    # 格式化数字字段
                    elif col_key in metrics and isinstance(value, (int, float)):
                        value = f"{value:,}"
                    formatted_row.append(value)
                formatted_rows.append(formatted_row)
            # 如果行是列表，直接格式化
            elif isinstance(row, list):
                formatted_row = []
                for i, value in enumerate(row):
                    col = columns[i] if i < len(columns) else ""
                    col_key = col.get("key", col) if isinstance(col, dict) else col
                    # 格式化日期字段（如果是时间戳）
                    col_key_lower = str(col_key).lower()
                    if (col_key_lower.find("date") != -1 or col_key_lower.find("time") != -1 or
                        col_key_lower.find("day") != -1 or col_key_lower.find("hour") != -1):
                        if isinstance(value, (int, float)) and analysis_plan and analysis_plan.time_range:
                            start_date = analysis_plan.time_range.start_date
                            end_date = analysis_plan.time_range.end_date
                            if start_date and end_date:
                                value = cls._format_date_timestamp(int(value), start_date, end_date)
                    # 格式化百分比字段
                    elif col_key in metrics and (col_key_lower.find("ctr") != -1 or col_key_lower.find("cvr") != -1):
                        if isinstance(value, (int, float)):
                            value = f"{value * 100:.1f}%"
                    # 格式化金额字段
                    elif col_key in metrics and (col_key_lower.find("cost") != -1 or col_key_lower.find("spend") != -1):
                        if isinstance(value, (int, float)):
                            value = f"¥{value:,.2f}"
                    # 格式化数字字段
                    elif col_key in metrics and isinstance(value, (int, float)):
                        value = f"{value:,}"
                    formatted_row.append(value)
                formatted_rows.append(formatted_row)
            else:
                formatted_rows.append(row)

        # 处理列格式 - 只提取 label 给前端显示（表头）
        # 同时保存原始key用于判断是否是ID列需要自动插入名称
        formatted_columns = []
        original_keys = []  # 保存每个列的原始key
        for col in columns:
            if isinstance(col, dict):
                label = col.get("label", col.get("key", str(col)))
                formatted_columns.append(label)
                original_keys.append(col.get("key", col.get("key", str(col))))
            else:
                formatted_columns.append(str(col))
                original_keys.append(str(col))

        # ---- 自动补充/修复维度名称（campaign_id → campaign_name 等） ----
        # ID 维度字段 -> (name列显示名, entity_type)
        id_to_name_map = {
            "campaign_id": ("计划名称", "campaign"),
            "adgroup_id": ("广告组名称", "adgroup"),
            "advertiser_id": ("广告主名称", "advertiser"),
            "creative_id": ("创意名称", "creative"),
        }

        # 名称列对应的entity_type
        # 各种可能的名称列原始key映射到对应的entity_type
        name_column_to_entity = {
            "campaign_name": "campaign",
            "adgroup_name": "adgroup",
            "advertiser_name": "advertiser",
            "creative_name": "creative",
            "campaign 名称": "campaign",  # 已经label化的也要处理
            "广告组名称": "adgroup",
            "广告主名称": "advertiser",
            "创意名称": "creative",
        }

        # 第一步：检查是否已经存在名称列，但是值仍然是ID，需要替换值
        # 我们需要找到ID列→名称列的对应关系
        id_to_name_column_idx: Dict[int, int] = {}  # id_column_idx -> name_column_idx

        for id_original_key, (_, entity_type) in id_to_name_map.items():
            # 查找是否已经存在对应名称列
            found = False
            for idx, (orig_key, col_label) in enumerate(zip(original_keys, formatted_columns)):
                # 判断这列是否是对应entity的名称列
                is_name_col = (orig_key in name_column_to_entity and name_column_to_entity[orig_key] == entity_type) or \
                             (col_label in name_column_to_entity and name_column_to_entity[col_label] == entity_type)
                if is_name_col:
                    # 查找对应的ID列在哪里
                    for id_idx, (id_orig_key, _) in enumerate(zip(original_keys, formatted_columns)):
                        if id_orig_key == id_original_key:
                            id_to_name_column_idx[id_idx] = idx
                            break
                    found = True
                    break  # 找到名称列，跳出当前循环
            # 找到后就不需要继续找了

        # 收集所有需要查询的实体和 ID
        entity_ids_by_type = {}
        name_needs_update = []  # [(id_col_idx, name_col_idx, entity_type)]

        for id_col_idx, name_col_idx in id_to_name_column_idx.items():
            # 从每行提取ID值，查询名称后更新到名称列
            for row in formatted_rows:
                if id_col_idx < len(row):
                    val = row[id_col_idx]
                    if val is not None and val != "":
                        # 找到这个ID列对应的entity_type
                        original_key = original_keys[id_col_idx]
                        _, entity_type = id_to_name_map[original_key]
                        if entity_type not in entity_ids_by_type:
                            entity_ids_by_type[entity_type] = set()
                        try:
                            entity_ids_by_type[entity_type].add(int(val))
                        except (ValueError, TypeError):
                            pass
                        name_needs_update.append((id_col_idx, name_col_idx, entity_type))

        # 第二步：对于没有名称列的纯ID列，需要在ID列后插入名称列
        name_insertions = []  # [(insert_after_idx, entity_type, name_col_name)]
        for current_idx, original_key in enumerate(original_keys):
            if original_key in id_to_name_map and current_idx not in id_to_name_column_idx:
                name_display, entity_type = id_to_name_map[original_key]
                name_insertions.append((current_idx, entity_type, name_display))
                # 也需要收集ID
                for row in formatted_rows:
                    if current_idx < len(row):
                        val = row[current_idx]
                        if val is not None and val != "":
                            if entity_type not in entity_ids_by_type:
                                entity_ids_by_type[entity_type] = set()
                            try:
                                entity_ids_by_type[entity_type].add(int(val))
                            except (ValueError, TypeError):
                                pass

        if entity_ids_by_type:
            # 批量查询所有 name
            name_maps = {}
            for entity_type, ids in entity_ids_by_type.items():
                if ids:
                    name_maps[entity_type] = get_entity_names(entity_type, list(ids))
                else:
                    name_maps[entity_type] = {}

            # 第一步：先更新已存在名称列的值（不影响索引）
            for id_col_idx, name_col_idx, entity_type in name_needs_update:
                name_map = name_maps.get(entity_type, {})
                for row in formatted_rows:
                    if id_col_idx < len(row) and name_col_idx < len(row):
                        try:
                            eid = int(row[id_col_idx])
                            ename = name_map.get(eid, str(row[id_col_idx]))
                            row[name_col_idx] = ename
                        except (ValueError, TypeError):
                            # 如果ID转换失败，保持原样
                            pass

            # 第二步：按位置从后往前插入新的名称列（避免索引偏移）
            for current_idx, entity_type, name_display in sorted(name_insertions, key=lambda x: -x[0]):
                name_map = name_maps.get(entity_type, {})
                formatted_columns.insert(current_idx + 1, name_display)
                for row in formatted_rows:
                    if current_idx < len(row):
                        try:
                            eid = int(row[current_idx])
                            ename = name_map.get(eid, "")
                        except (ValueError, TypeError):
                            ename = ""
                        row.insert(current_idx + 1, ename)

        return {
            "columns": formatted_columns,
            "rows": formatted_rows
        }

    @classmethod
    def _generate_highlights(
        cls,
        data: List[Dict[str, Any]],
        metrics: List[str],
        quality_result: QualityResult,
        data_table: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """生成亮点（基于规则）"""
        highlights = []

        # 1. 从数据生成亮点
        data_highlights = cls._generate_highlights_from_data(data, metrics)
        highlights.extend(data_highlights)

        # 2. 从质量问题生成警告
        for issue in quality_result.issues:
            if issue.severity == "warning":
                highlights.append({
                    "type": "warning",
                    "text": f"⚠️ {issue.message}"
                })
            elif issue.severity == "hitl_required":
                highlights.append({
                    "type": "info",
                    "text": f"ℹ️ {issue.message}"
                })

        # 3. 添加质量警告
        for warning in quality_result.warnings:
            highlights.append({
                "type": "warning",
                "text": f"⚠️ {warning}"
            })

        # 4. 如果没有任何亮点，添加默认提示
        if not highlights:
            # 如果 data 为空但 data_table 有数据，使用 data_table 的行数
            total_records = len(data)
            if total_records == 0 and data_table and "rows" in data_table:
                total_records = len(data_table["rows"])

            if total_records > 0:
                highlights.append({
                    "type": "info",
                    "text": "✅ 数据加载完成，共 {} 条记录".format(total_records)
                })
            else:
                highlights.append({
                    "type": "info",
                    "text": "📭 当前条件下无数据，建议调整筛选条件"
                })

        return highlights

    @classmethod
    def _generate_highlights_from_data(
        cls,
        data: List[Dict[str, Any]],
        metrics: List[str]
    ) -> List[Dict[str, str]]:
        """基于数据生成亮点"""
        highlights = []

        if not data or not metrics:
            return highlights

        # 1. 总体统计
        total_records = len(data)
        if total_records > 0:
            highlights.append({
                "type": "info",
                "text": f"📊 共 {total_records} 条数据记录"
            })

        # 2. 指标汇总（处理前2个指标）
        for metric in metrics[:2]:  # 只处理前2个指标，避免亮点太多
            values = []
            for row in data:
                val = row.get(metric)
                if isinstance(val, (int, float)):
                    values.append(val)

            if values:
                total = sum(values)
                avg = total / len(values)
                max_val = max(values)
                min_val = min(values)

                # 格式化数值
                if metric.lower().find("ctr") != -1 or metric.lower().find("cvr") != -1:
                    total_str = f"{total * 100:.1f}%"
                    avg_str = f"{avg * 100:.1f}%"
                    max_str = f"{max_val * 100:.1f}%"
                    min_str = f"{min_val * 100:.1f}%"
                elif metric.lower().find("cost") != -1:
                    total_str = f"¥{total:,.2f}"
                    avg_str = f"¥{avg:,.2f}"
                    max_str = f"¥{max_val:,.2f}"
                    min_str = f"¥{min_val:,.2f}"
                else:
                    total_str = f"{total:,.0f}"
                    avg_str = f"{avg:,.0f}"
                    max_str = f"{max_val:,.0f}"
                    min_str = f"{min_val:,.0f}"

                metric_display_name = cls._get_metric_display_name(metric)

                if len(values) > 1:
                    highlights.append({
                        "type": "info",
                        "text": f"📈 {metric_display_name}：总计 {total_str}，平均 {avg_str}，最高 {max_str}，最低 {min_str}"
                    })
                else:
                    highlights.append({
                        "type": "info",
                        "text": f"📈 {metric_display_name}：{total_str}"
                    })

        # 3. 趋势判断（如果有日期字段且数据>=3条，使用第一个指标）
        primary_metric = metrics[0] if metrics else None
        if len(data) >= 3 and primary_metric:
            date_fields = ["date", "data_date", "day", "data_day"]
            has_date_field = any(f in data[0] for f in date_fields)

            if has_date_field:
                # 简单的趋势判断：比较前半部分和后半部分的平均值
                mid = len(data) // 2
                first_half = data[:mid]
                second_half = data[mid:]

                first_values = [row.get(primary_metric, 0) for row in first_half if isinstance(row.get(primary_metric), (int, float))]
                second_values = [row.get(primary_metric, 0) for row in second_half if isinstance(row.get(primary_metric), (int, float))]

                if first_values and second_values:
                    first_avg = sum(first_values) / len(first_values)
                    second_avg = sum(second_values) / len(second_values)

                    if second_avg > first_avg * 1.1:  # 上升超过10%
                        highlights.append({
                            "type": "positive",
                            "text": f"🟢 {cls._get_metric_display_name(primary_metric)} 呈现上升趋势"
                        })
                    elif second_avg < first_avg * 0.9:  # 下降超过10%
                        highlights.append({
                            "type": "negative",
                            "text": f"🔴 {cls._get_metric_display_name(primary_metric)} 呈现下降趋势"
                        })

        return highlights[:5]  # 最多返回5个亮点

    @classmethod
    def _get_metric_display_name(cls, metric: str) -> str:
        """获取指标显示名称"""
        display_names = {
            "cost": "消耗",
            "impressions": "曝光量",
            "clicks": "点击量",
            "ctr": "点击率",
            "cvr": "转化率",
            "spend": "花费",
            "conv": "转化数",
        }
        return display_names.get(metric, metric)

    @classmethod
    def _format_date_timestamp(cls, timestamp: int, start_date: str, end_date: str) -> str:
        """格式化日期时间戳

        根据时间范围跨度选择粒度：
        - 跨度 > 1天 → 格式化为 YYYY-MM-DD
        - 跨度 ≤ 1天 → 格式化为 YYYY-MM-DD HH
        """
        from datetime import datetime, timedelta

        try:
            # 解析起始和结束日期
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days_diff = (end_dt - start_dt).days
        except (ValueError, TypeError):
            # 如果解析失败，默认按日格式化
            days_diff = 2

        # timestamp 可能是毫秒或秒
        if timestamp > 1e12:  # 毫秒
            dt = datetime.fromtimestamp(timestamp / 1000)
        else:  # 秒
            dt = datetime.fromtimestamp(timestamp)

        if days_diff > 1:
            return dt.strftime("%Y-%m-%d")
        else:
            return dt.strftime("%Y-%m-%d %H")

    @classmethod
    def _format_quality_info(cls, quality_result: QualityResult) -> Dict[str, Any]:
        """格式化质量信息"""
        return {
            "passed": quality_result.passed,
            "issues": [
                {
                    "check_type": issue.check_type.value if hasattr(issue.check_type, "value") else issue.check_type,
                    "severity": issue.severity,
                    "message": issue.message,
                    "suggested_action": issue.suggested_action.value if hasattr(issue.suggested_action, "value") else issue.suggested_action,
                    "threshold": issue.threshold,
                    "actual": issue.actual
                }
                for issue in quality_result.issues
            ],
            "warnings": quality_result.warnings,
            "actions": [action.value if hasattr(action, "value") else action for action in quality_result.actions]
        }

    @classmethod
    def _generate_metadata(cls, filter_result: FilterResult, analysis_plan: AnalysisPlan, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """生成元数据"""
        # Get actual chart type from the built chart_config by backend
        # If chart_config has no type, fall back to analysis_plan.chart_type
        chart_type = (
            chart_config.get("type",
                analysis_plan.chart_config.type.value if hasattr(analysis_plan.chart_config, "type") and hasattr(analysis_plan.chart_config.type, "value")
                else analysis_plan.chart_config.type if analysis_plan.chart_config is not None and hasattr(analysis_plan.chart_config, "type")
                else analysis_plan.chart_config if analysis_plan.chart_config is not None
                else "table"
            )
        )
        return {
            "generated_at": datetime.now().isoformat(),
            "entity_level": filter_result.entity_level,
            "total_entities": filter_result.total_count,
            "metrics": analysis_plan.metrics,
            "analysis_type": analysis_plan.analysis_type.value if hasattr(analysis_plan.analysis_type, "value") else analysis_plan.analysis_type,
            "chart_type": chart_type,
            "time_range": {
                "start_date": analysis_plan.time_range.start_date,
                "end_date": analysis_plan.time_range.end_date,
                "granularity": analysis_plan.time_range.granularity
            }
        }

    @classmethod
    def _summarize_cot_reasoning(cls, cot_reasoning: Optional[CotReasoning]) -> Optional[str]:
        """摘要 CoT 推理过程"""
        if not cot_reasoning:
            return None

        if cot_reasoning.summary:
            return cot_reasoning.summary

        # 如果没有摘要，从步骤中生成
        if cot_reasoning.steps:
            return " → ".join([step.step_name for step in cot_reasoning.steps])

        return None

    @classmethod
    def _generate_next_queries(cls, analysis_plan: AnalysisPlan, data: List[Dict[str, Any]]) -> List[str]:
        """生成推荐查询"""
        next_queries = []

        if analysis_plan.analysis_type == AnalysisType.TIME_TREND:
            next_queries.append("按广告计划维度拆分趋势")
            next_queries.append("对比上周同期数据")
            next_queries.append("查看受众分布情况")
        elif analysis_plan.analysis_type == AnalysisType.ENTITY_TABLE:
            next_queries.append("查看时间趋势变化")
            next_queries.append("对比不同时期表现")
            next_queries.append("下钻到广告组维度")
        elif analysis_plan.analysis_type == AnalysisType.PERIOD_COMPARISON:
            next_queries.append("查看详细趋势图")
            next_queries.append("按维度拆分对比")
            next_queries.append("查看受众对比")
        elif analysis_plan.analysis_type == AnalysisType.AUDIENCE_DISTRIBUTION:
            next_queries.append("查看不同受众的转化情况")
            next_queries.append("对比历史受众分布")
            next_queries.append("按受众查看趋势")
        else:
            next_queries.append("查看时间趋势")
            next_queries.append("对比分析")
            next_queries.append("查看受众分布")

        return next_queries
