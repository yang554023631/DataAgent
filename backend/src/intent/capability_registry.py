"""
系统能力注册表 — 记录系统支持的指标、层级、维度、时间范围等

报表意图识别用这个注册表做能力校验，不支持的内容触发澄清。
"""
from typing import Dict, List, Tuple, Optional

# 从现有规则工具导入映射关系，保持一致性
from src.tools.term_mapper import METRIC_MAPPING, DIMENSION_MAPPING


# ========== 广告层级 ==========

# 标准名 -> 中文别名
AD_LEVEL_MAP: Dict[str, List[str]] = {
    "campaign": ["计划", "广告计划", "活动", "广告活动", "campaign"],
    "ad_group": ["广告组", "组", "adgroup", "ad_group"],
    "creative": ["创意", "素材", "creative", "creatives"],
}

SUPPORTED_AD_LEVELS: List[str] = list(AD_LEVEL_MAP.keys())


def _build_alias_map(standard_to_aliases: Dict[str, List[str]]) -> Dict[str, str]:
    """从 {标准名: [别名]} 构建 {别名: 标准名} 映射"""
    alias_map = {}
    for std, aliases in standard_to_aliases.items():
        # 标准名自己也加入映射
        alias_map[std.lower()] = std
        for alias in aliases:
            alias_map[alias.lower()] = std
    return alias_map


_ad_level_alias_map = _build_alias_map(AD_LEVEL_MAP)


def validate_ad_level(name: str) -> Tuple[bool, Optional[str]]:
    """
    校验广告层级是否支持

    Returns:
        (是否支持, 标准名)
    """
    if not name:
        return False, None
    key = name.lower()
    if key in _ad_level_alias_map:
        return True, _ad_level_alias_map[key]
    return False, None


# ========== 指标 ==========

# 把 METRIC_MAPPING（别名->标准）转换成 标准->[别名] 格式
_metric_standard_to_aliases: Dict[str, List[str]] = {}
for alias, standard in METRIC_MAPPING.items():
    if standard not in _metric_standard_to_aliases:
        _metric_standard_to_aliases[standard] = []
    _metric_standard_to_aliases[standard].append(alias)

SUPPORTED_METRICS: Dict[str, List[str]] = _metric_standard_to_aliases


def _build_metric_alias_map() -> Dict[str, str]:
    """构建 {别名: 标准名} 的指标映射"""
    alias_map = {}
    for standard, aliases in SUPPORTED_METRICS.items():
        alias_map[standard.lower()] = standard
        for alias in aliases:
            alias_map[alias.lower()] = standard
    return alias_map


_metric_alias_map = _build_metric_alias_map()


def validate_metric(name: str) -> Tuple[bool, Optional[str]]:
    """
    校验指标是否支持

    Returns:
        (是否支持, 标准名)
    """
    if not name:
        return False, None
    key = name.lower()
    if key in _metric_alias_map:
        return True, _metric_alias_map[key]
    return False, None


def get_metric_aliases() -> Dict[str, str]:
    """获取 {别名: 标准名} 的完整映射"""
    return _metric_alias_map.copy()


def get_all_metric_names() -> List[str]:
    """获取所有指标的中文名称列表（用于澄清选项）"""
    all_names = []
    for standard, aliases in SUPPORTED_METRICS.items():
        cn_aliases = [a for a in aliases if not (a.replace("_", "").isascii() and a.replace("_", "").isalpha())]
        all_names.extend(cn_aliases)
    # 去重
    return list(set(all_names))


# ========== 维度 ==========

# 把 DIMENSION_MAPPING 转换成 标准->[别名]
_dimension_standard_to_aliases: Dict[str, List[str]] = {}
for alias, standard in DIMENSION_MAPPING.items():
    if standard not in _dimension_standard_to_aliases:
        _dimension_standard_to_aliases[standard] = []
    _dimension_standard_to_aliases[standard].append(alias)

SUPPORTED_DIMENSIONS: Dict[str, List[str]] = _dimension_standard_to_aliases


def _build_dimension_alias_map() -> Dict[str, str]:
    alias_map = {}
    for standard, aliases in SUPPORTED_DIMENSIONS.items():
        alias_map[standard.lower()] = standard
        for alias in aliases:
            alias_map[alias.lower()] = standard
    return alias_map


_dimension_alias_map = _build_dimension_alias_map()


def validate_dimension(name: str) -> Tuple[bool, Optional[str]]:
    """
    校验维度是否支持

    Returns:
        (是否支持, 标准名)
    """
    if not name:
        return False, None
    key = name.lower()
    if key in _dimension_alias_map:
        return True, _dimension_alias_map[key]
    return False, None


def get_all_dimension_names() -> List[str]:
    """获取所有维度的主要中文名称列表"""
    primary_names = []
    for standard, aliases in SUPPORTED_DIMENSIONS.items():
        cn_aliases = [a for a in aliases if not (a.replace("_", "").isascii() and a.replace("_", "").isalpha())]
        if cn_aliases:
            primary_names.append(cn_aliases[0])
        else:
            primary_names.append(standard)
    return primary_names


# ========== 时间粒度 ==========

SUPPORTED_TIME_UNITS: List[str] = ["day", "week", "month"]
TIME_UNIT_ALIASES: Dict[str, str] = {
    "天": "day", "日": "day", "按天": "day", "每天": "day",
    "周": "week", "按周": "week", "每周": "week",
    "月": "month", "按月": "month", "每月": "month",
}