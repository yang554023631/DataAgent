"""DSL 安全校验器

四层防护中的第2层：DSL 结构校验。
对生成的 ES DSL 进行静态检查，确保只读、有必要过滤、不超限。
"""
import logging
from typing import List, Set, Optional

logger = logging.getLogger(__name__)


class ValidationResult:
    """校验结果"""

    def __init__(self):
        self.ok: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, msg: str):
        self.ok = False
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def __repr__(self):
        return f"ValidationResult(ok={self.ok}, errors={self.errors}, warnings={self.warnings})"


class DslValidator:
    """ES DSL 安全校验器

    校验规则：
    1. 索引白名单校验
    2. 必须包含 advertiser_id 过滤
    3. 必须包含时间范围过滤
    4. 禁止 script / script_fields
    5. size / agg size 上限检查（warning 级别，执行器负责截断）
    6. DSL 结构合法性检查（必须是 dict）
    """

    # 禁止的顶层 key（写操作 / 脚本）
    FORBIDDEN_TOP_LEVEL_KEYS = {
        "script", "script_fields", "update", "doc", "upsert",
        "source_to_create", "_source",
    }

    # 禁止的 query 类型（写操作相关）
    FORBIDDEN_QUERY_KEYS = {
        "script",
    }

    def __init__(
        self,
        allowed_indices: Set[str] = None,
        max_size: int = 1000,
        max_agg_size: int = 500,
        require_advertiser_filter: bool = True,
        require_time_filter: bool = True,
    ):
        self.allowed_indices = allowed_indices or set()
        self.max_size = max_size
        self.max_agg_size = max_agg_size
        self.require_advertiser_filter = require_advertiser_filter
        self.require_time_filter = require_time_filter

    def validate(self, dsl: dict, index_name: str) -> ValidationResult:
        """校验 DSL

        Args:
            dsl: ES DSL 字典
            index_name: 要查询的索引名

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # 1. 结构合法性
        if not isinstance(dsl, dict):
            result.add_error("DSL 不是合法的字典对象")
            return result

        # 2. 索引白名单
        if self.allowed_indices and index_name not in self.allowed_indices:
            result.add_error(
                f"索引 '{index_name}' 不在查询白名单中。"
                f"允许的索引: {sorted(self.allowed_indices)}"
            )

        # 3. 禁止的顶层 key
        for key in self.FORBIDDEN_TOP_LEVEL_KEYS:
            if key in dsl:
                result.add_error(f"禁止使用 '{key}'，不允许脚本或写操作")

        # 4. query 部分校验
        query = dsl.get("query", {})
        if query:
            self._check_query_forbidden_keys(query, result)
            if self.require_advertiser_filter:
                self._check_advertiser_filter(query, result)
            if self.require_time_filter:
                self._check_time_filter(query, result)

        # 5. size 上限
        size = dsl.get("size", 10)
        if isinstance(size, int) and size > self.max_size:
            result.add_warning(
                f"size={size} 超过上限 {self.max_size}，将被自动截断"
            )

        # 6. aggs size 上限
        aggs = dsl.get("aggs") or dsl.get("aggregations")
        if aggs:
            self._check_agg_sizes(aggs, result)

        logger.info(
            f"DSL校验: 索引={index_name}, ok={result.ok}, "
            f"错误数={len(result.errors)}, 警告数={len(result.warnings)}"
        )
        return result

    def _check_query_forbidden_keys(self, query: dict, result: ValidationResult):
        """检查 query 中是否有禁用的 key"""
        if not isinstance(query, dict):
            return
        for key in query:
            if key in self.FORBIDDEN_QUERY_KEYS:
                result.add_error(f"query 中禁止使用 '{key}'")
                return
            # 递归检查 bool 的各子句
            if key == "bool" and isinstance(query[key], dict):
                for clause in ["must", "must_not", "should", "filter"]:
                    items = query[key].get(clause, [])
                    if isinstance(items, list):
                        for item in items:
                            self._check_query_forbidden_keys(item, result)

    def _check_advertiser_filter(self, query: dict, result: ValidationResult):
        """检查是否包含 advertiser_id 过滤"""
        found = self._find_field_in_query(query, "advertiser_id")
        if not found:
            result.add_error("缺少 advertiser_id 过滤条件，不允许全平台查询")

    def _check_time_filter(self, query: dict, result: ValidationResult):
        """检查是否包含时间范围过滤"""
        found = self._find_field_in_query(query, "data_date")
        if not found:
            result.add_error("缺少 data_date 时间范围过滤条件")

    def _find_field_in_query(self, query: dict, field_name: str) -> bool:
        """递归查找 query 中是否包含某个字段的过滤"""
        if not isinstance(query, dict):
            return False

        # term / terms
        for key in ["term", "terms"]:
            if key in query and isinstance(query[key], dict):
                if field_name in query[key]:
                    return True

        # range
        if "range" in query and isinstance(query["range"], dict):
            if field_name in query["range"]:
                return True

        # bool 子句
        if "bool" in query and isinstance(query["bool"], dict):
            for clause in ["must", "must_not", "should", "filter"]:
                items = query["bool"].get(clause, [])
                if isinstance(items, list):
                    for item in items:
                        if self._find_field_in_query(item, field_name):
                            return True

        # nested
        if "nested" in query and isinstance(query["nested"], dict):
            return self._find_field_in_query(query["nested"].get("query", {}), field_name)

        return False

    def _check_agg_sizes(self, aggs: dict, result: ValidationResult):
        """递归检查所有 terms agg 的 size 是否超限"""
        if not isinstance(aggs, dict):
            return
        for agg_name, agg_body in aggs.items():
            if not isinstance(agg_body, dict):
                continue
            # terms agg
            if "terms" in agg_body and isinstance(agg_body["terms"], dict):
                size = agg_body["terms"].get("size", 10)
                if isinstance(size, int) and size > self.max_agg_size:
                    result.add_warning(
                        f"聚合 '{agg_name}' 的 size={size} 超过上限 {self.max_agg_size}，将被自动截断"
                    )
            # 递归检查嵌套 aggs
            for nested_key in ["aggs", "aggregations"]:
                nested = agg_body.get(nested_key)
                if nested:
                    self._check_agg_sizes(nested, result)