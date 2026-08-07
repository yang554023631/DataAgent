"""ES 查询结果格式化器

将 ES 原始响应转成统一的中间格式，
并自动判断或按提示确定呈现类型。
"""
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ResultFormatter:
    """ES 查询结果格式化器"""

    @classmethod
    def format(
        cls,
        es_response: dict,
        display_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """格式化 ES 响应

        Args:
            es_response: ES 原始响应字典
            display_type: 呈现类型提示，若为 None 则自动检测

        Returns:
            {
                "display_type": str,
                "columns": List[str],
                "rows": List[List[Any]],
                "metadata": {
                    "total_rows": int,
                    "has_aggregations": bool,
                }
            }
        """
        if not display_type:
            display_type = cls._detect_display_type(es_response)

        # 如果有聚合结果且没有命中列表（size=0 的纯聚合查询），优先按聚合处理
        if cls._is_aggregation_result(es_response) and not cls._has_hit_documents(es_response):
            columns, rows = cls._format_aggregations(es_response, display_type)
            total = len(rows)
        elif cls._has_hit_documents(es_response):
            columns, rows = cls._format_hits(es_response)
            total = cls._get_hits_total(es_response)
        elif cls._is_aggregation_result(es_response):
            columns, rows = cls._format_aggregations(es_response, display_type)
            total = len(rows)
        else:
            columns, rows = [], []
            total = 0

        return {
            "display_type": display_type,
            "columns": columns,
            "rows": rows,
            "metadata": {
                "total_rows": total,
                "has_aggregations": cls._is_aggregation_result(es_response),
            },
        }

    # ---- 检测方法 ----

    @staticmethod
    def _detect_display_type(es_response: dict) -> str:
        """自动检测呈现类型"""
        if not ResultFormatter._is_aggregation_result(es_response):
            # 纯命中 → 列表
            return "list"

        aggs = es_response.get("aggregations", {})
        # 检查是否有 date_histogram
        if ResultFormatter._has_date_histogram(aggs):
            return "trend"

        # 检查是否有任意桶聚合（包括 terms、filters 等）
        if ResultFormatter._has_bucket_aggregations(aggs):
            return "comparison"

        # 单值聚合 → QA
        if ResultFormatter._has_single_value_agg(aggs):
            return "qa"

        return "detail"

    @staticmethod
    def _has_bucket_aggregations(aggs: dict) -> bool:
        """递归检测是否有任意包含 buckets 的聚合"""
        if not isinstance(aggs, dict):
            return False
        for key, val in aggs.items():
            if not isinstance(val, dict):
                continue
            if "buckets" in val:
                # 排除已经被检测为 date_histogram 的情况
                if not ResultFormatter._has_date_histogram({key: val}):
                    return True
            for nested_key in ["aggs", "aggregations"]:
                nested = val.get(nested_key)
                if nested and ResultFormatter._has_bucket_aggregations(nested):
                    return True
        return False

    @staticmethod
    def _has_hit_documents(es_response: dict) -> bool:
        """是否有实际的命中文档（hits.hits 非空）

        注意：size=0 的聚合查询 hits.total 可能很大，但 hits.hits 为空，
        这种情况不算命中结果。
        """
        return len(es_response.get("hits", {}).get("hits", [])) > 0

    @staticmethod
    def _is_hits_result(es_response: dict) -> bool:
        """是否是命中结果为主（非聚合查询）

        保持向后兼容，调用 _has_hit_documents。
        """
        return ResultFormatter._has_hit_documents(es_response)

    @staticmethod
    def _is_aggregation_result(es_response: dict) -> bool:
        """是否是聚合结果为主"""
        aggs = es_response.get("aggregations") or es_response.get("aggs")
        return bool(aggs)

    @staticmethod
    def _has_date_histogram(aggs: dict) -> bool:
        """递归检测是否有 date_histogram 聚合"""
        if not isinstance(aggs, dict):
            return False
        for key, val in aggs.items():
            if not isinstance(val, dict):
                continue
            if "date_histogram" in val:
                return True
            # 检测简化的 date histogram 格式（直接有 buckets）
            if "buckets" in val and key.lower().find("date") != -1:
                return True
            for nested_key in ["aggs", "aggregations"]:
                nested = val.get(nested_key)
                if nested and ResultFormatter._has_date_histogram(nested):
                    return True
        return False

    @staticmethod
    def _has_terms_agg(aggs: dict) -> bool:
        """递归检测是否有 terms 聚合"""
        if not isinstance(aggs, dict):
            return False
        for key, val in aggs.items():
            if not isinstance(val, dict):
                continue
            if "terms" in val:
                return True
            for nested_key in ["aggs", "aggregations"]:
                nested = val.get(nested_key)
                if nested and ResultFormatter._has_terms_agg(nested):
                    return True
        return False

    @staticmethod
    def _has_single_value_agg(aggs: dict) -> bool:
        """检测是否是单值聚合（sum/avg/count 等，无 buckets）"""
        if not isinstance(aggs, dict):
            return False
        for key, val in aggs.items():
            if not isinstance(val, dict):
                continue
            # 有 value 字段但没有 buckets → 单值
            if "value" in val and "buckets" not in val:
                return True
        return False

    # ---- 格式化方法 ----

    @staticmethod
    def _format_hits(es_response: dict) -> tuple:
        """格式化命中结果为 (columns, rows)"""
        hits = es_response.get("hits", {}).get("hits", [])
        if not hits:
            return [], []

        # 收集所有字段名
        columns_set = []
        for hit in hits:
            source = hit.get("_source", {})
            for key in source.keys():
                if key not in columns_set:
                    columns_set.append(key)

        # 排序以保证列顺序稳定
        columns = sorted(columns_set)
        rows = []
        for hit in hits:
            source = hit.get("_source", {})
            row = [source.get(col, "") for col in columns]
            rows.append(row)

        return columns, rows

    @staticmethod
    def _format_aggregations(es_response: dict, display_type: str) -> tuple:
        """格式化聚合结果为 (columns, rows)

        简化策略：找到第一个（最外层）有 buckets 的聚合，
        将其 buckets 拍平为表格行。
        """
        aggs = es_response.get("aggregations", {})
        if not aggs:
            return [], []

        # 找到第一个有 buckets 或 value 的聚合
        first_agg_name = list(aggs.keys())[0]
        first_agg = aggs[first_agg_name]

        if "buckets" in first_agg:
            return ResultFormatter._flatten_buckets(first_agg["buckets"], first_agg_name)
        elif "value" in first_agg:
            # 单值聚合
            return ["指标", "数值"], [[first_agg_name, first_agg["value"]]]

        return [], []

    @staticmethod
    def _flatten_buckets(buckets: list, agg_name: str) -> tuple:
        """将 buckets 拍平为 (columns, rows)

        递归一层：如果 bucket 里还有嵌套的单值子聚合，也提取出来作为列。
        """
        if not buckets:
            return [], []

        # 从第一个 bucket 推导列
        first = buckets[0]
        # 使用原始聚合名称作为列名
        key_label = agg_name
        columns = [key_label]
        value_agg_names = []

        for key, val in first.items():
            if key in ("key", "key_as_string", "doc_count"):
                continue
            if isinstance(val, dict) and "value" in val:
                columns.append(key)
                value_agg_names.append(key)

        rows = []
        for bucket in buckets:
            key_val = bucket.get("key_as_string", bucket.get("key", ""))
            row = [key_val]
            for agg_name_col in value_agg_names:
                val = bucket.get(agg_name_col, {}).get("value", 0)
                row.append(val)
            rows.append(row)

        return columns, rows

    @staticmethod
    def _get_hits_total(es_response: dict) -> int:
        """获取命中总数"""
        total = es_response.get("hits", {}).get("total", 0)
        if isinstance(total, dict):
            return total.get("value", 0)
        return total
