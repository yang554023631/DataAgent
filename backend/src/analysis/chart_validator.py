"""
Chart Data Structure Validator

按 chart_type 校验报告数据结构，确保返回给前端的数据结构正确：
- line/bar/pie 图表：必须有非空数据，每个点必须有必填字段，不允许 null 指标值
- table：必须有 columns/rows，行列数匹配，允许空结果
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ChartValidationResult:
    """校验结果"""
    def __init__(self):
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_chart_report(report_data: Dict[str, Any]) -> ChartValidationResult:
    """
    校验完整图表报告结构，根据 chart_type 做相应校验

    Args:
        report_data: final_report 数据，包含 metadata, chart_config, data, data_table

    Returns:
        ChartValidationResult
    """
    result = ChartValidationResult()

    metadata = report_data.get("metadata", {})
    # Get chart_config from report, ensure it's never None - convert to empty dict
    chart_config = report_data.get("chart_config")
    if chart_config is None:
        chart_config = {}
    data = report_data.get("data", [])
    data_table = report_data.get("data_table", {})

    # Extra guarantee - if it's still not a dict, make it one
    if not isinstance(chart_config, dict):
        chart_config = {}

    # Debug log
    logger.debug(f"[DEBUG] validate_chart_report: chart_config={type(chart_config)}, chart_type={metadata.get('chart_type')}")

    chart_type = metadata.get("chart_type")

    if not chart_type:
        # fallback 到 chart_config.type
        chart_type = chart_config.get("type") if chart_config else None

    if not chart_type:
        result.add_error("Missing chart_type in metadata.chart_type or chart_config.type")
        return result

    # Final guarantee - any chart getting called must have dict chart_config
    if chart_config is None:
        chart_config = {}
    if not isinstance(chart_config, dict):
        chart_config = {}

    # 按类型分发校验
    if chart_type == "line":
        _validate_line_data(data, result)
    elif chart_type == "bar":
        _validate_bar_data(data, chart_config, result)
    elif chart_type == "pie":
        _validate_pie_data(data, result)
    elif chart_type == "table":
        _validate_table_data(data_table, result)
    else:
        result.add_warning(f"Unknown chart_type: {chart_type}, no validation performed")

    # 输出日志
    if not result.is_valid:
        for err in result.errors:
            logger.error(f"[ChartValidation] {err}")
    for warn in result.warnings:
        logger.warning(f"[ChartValidation] {warn}")

    return result


def _validate_line_data(data: List[Any], result: ChartValidationResult) -> None:
    """校验折线图结构"""
    if not isinstance(data, list):
        result.add_error("line chart: data must be a list")
        return

    if len(data) == 0:
        result.add_error("line chart: data array is empty (line chart requires data)")
        return

    for i, point in enumerate(data):
        if not isinstance(point, dict):
            result.add_error(f"line chart: point[{i}] is not an object")
            continue

        if "date" not in point:
            result.add_error(f"line chart: point[{i}] missing required 'date' field")
        else:
            if point["date"] is None:
                result.add_error(f"line chart: point[{i}].date is null (not allowed)")

        # 检查每个非-date 字段不能为 null
        for k, v in point.items():
            if k != "date" and v is None:
                result.add_error(f"line chart: point[{i}].{k} is null (not allowed for chart metrics)")

    # 检查至少有一个非-date 字段
    if len(data) > 0 and isinstance(data[0], dict):
        non_date_fields = [k for k in data[0].keys() if k != "date"]
        if len(non_date_fields) == 0:
            result.add_error("line chart: no metric fields found (only 'date' exists)")


def _validate_bar_data(data: List[Any], chart_config: Dict[str, Any], result: ChartValidationResult) -> None:
    """校验柱状图结构"""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"=== ENTER _validate_bar_data: chart_config={chart_config}, type={type(chart_config)} ===")

    if not isinstance(data, list):
        result.add_error("bar chart: data must be a list")
        return

    if len(data) == 0:
        result.add_error("bar chart: data array is empty (bar chart requires data)")
        return

    # Ultimate guard: if it's not a dict at all, force it to empty dict
    if chart_config is None or not isinstance(chart_config, dict):
        logger.error(f"=== Converting chart_config from {type(chart_config)} to empty dict ===")
        chart_config = {}

    # Debug: crash if still None
    if chart_config is None:
        raise RuntimeError(f"Failed to convert chart_config from None to dict! type={type(chart_config)}")

    # 检查 chart_config 必须有 x_axis.field 和 y_axis.field
    x_axis = chart_config.get("x_axis")
    x_field = x_axis.get("field") if x_axis and isinstance(x_axis, dict) else None
    y_axis = chart_config.get("y_axis")
    y_field = y_axis.get("field") if y_axis and isinstance(y_axis, dict) else None

    if not x_field:
        result.add_error("bar chart: chart_config.x_axis.field is missing")
    if not y_field:
        result.add_error("bar chart: chart_config.y_axis.field is missing")

    # 每个点必须有 x, y 字段，且值不能为 null
    for i, point in enumerate(data):
        if not isinstance(point, dict):
            result.add_error(f"bar chart: point[{i}] is not an object")
            continue

        if x_field:
            if x_field not in point:
                result.add_error(f"bar chart: point[{i}] missing x_axis.field '{x_field}'")
            elif point[x_field] is None:
                result.add_error(f"bar chart: point[{i}].{x_field} is null (not allowed)")

        if y_field:
            if y_field not in point:
                result.add_error(f"bar chart: point[{i}] missing y_axis.field '{y_field}'")
            elif point[y_field] is None:
                result.add_error(f"bar chart: point[{i}].{y_field} is null (not allowed for chart metrics)")


def _validate_pie_data(data: List[Any], result: ChartValidationResult) -> None:
    """校验饼图结构"""
    if not isinstance(data, list):
        result.add_error("pie chart: data must be a list")
        return

    if len(data) == 0:
        result.add_error("pie chart: data array is empty (pie chart requires data)")
        return

    for i, point in enumerate(data):
        if not isinstance(point, dict):
            result.add_error(f"pie chart: point[{i}] is not an object")
            continue

        if "label" not in point:
            result.add_error(f"pie chart: point[{i}] missing required 'label' field")
        elif point["label"] is None:
            result.add_error(f"pie chart: point[{i}].label is null (not allowed)")

        if "value" not in point:
            result.add_error(f"pie chart: point[{i}] missing required 'value' field")
        elif point["value"] is None:
            result.add_error(f"pie chart: point[{i}].value is null (not allowed for chart metrics)")


def _validate_table_data(data_table: Dict[str, Any], result: ChartValidationResult) -> None:
    """校验表格结构"""
    if not isinstance(data_table, dict):
        result.add_error("table chart: data_table must be an object")
        return

    if "columns" not in data_table:
        result.add_error("table chart: data_table missing 'columns' field")
        return
    if not isinstance(data_table["columns"], list):
        result.add_error("table chart: data_table.columns must be a list")
        return
    if len(data_table["columns"]) == 0:
        result.add_error("table chart: data_table.columns is empty (need at least one column)")
        return

    if "rows" not in data_table:
        result.add_error("table chart: data_table missing 'rows' field")
        return
    if not isinstance(data_table["rows"], list):
        result.add_error("table chart: data_table.rows must be a list")
        return

    # 检查每行列数匹配 columns
    expected_cols = len(data_table["columns"])
    for i, row in enumerate(data_table["rows"]):
        if not isinstance(row, (list, tuple)):
            result.add_error(f"table chart: row[{i}] is not a list/tuple")
            continue
        if len(row) != expected_cols:
            result.add_error(
                f"table chart: row[{i}] column count mismatch: "
                f"expected {expected_cols}, got {len(row)}"
            )
