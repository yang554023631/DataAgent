"""
IntentAnalyzer - 轻量级字段提取和场景识别

在 CoT 规划之前进行初步的字段提取，减少 LLM 的工作量。
使用规则 + LLM 辅助的混合方法。
"""
import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, timedelta
from dataclasses import dataclass
from enum import Enum

from src.analysis.models import (
    FieldContext,
    AnalysisTimeRange,
    AnalysisType,
    FilterType,
    EntityLevel
)

logger = logging.getLogger(__name__)

# ==================== 嵌入必要的映射数据 ====================

# 指标映射（从 term_mapper 复制）
METRIC_MAPPING = {
    "曝光": "impressions",
    "展示": "impressions",
    "展示量": "impressions",
    "impression": "impressions",
    "点击": "clicks",
    "点击量": "clicks",
    "click": "clicks",
    "花费": "cost",
    "消耗": "cost",
    "消费": "cost",
    "成本": "cost",
    "转化": "conversions",
    "转化数": "conversions",
    "转化量": "conversions",
    "conversion": "conversions",
    "覆盖": "reach",
    "覆盖人数": "reach",
    "覆盖量": "reach",
    "触达": "reach",
    "触达人数": "reach",
    "触达量": "reach",
    "reach": "reach",
    "Reach": "reach",
    "频次": "frequency",
    "曝光频次": "frequency",
    "frequency": "frequency",
    "Frequency": "frequency",
    "点击率": "ctr",
    "CTR": "ctr",
    "转化率": "cvr",
    "CVR": "cvr",
    "投产比": "roi",
    "ROI": "roi",
}

# 层级映射（从 capability_registry 复制）
AD_LEVEL_MAP = {
    "campaign": ["计划", "广告计划", "活动", "广告活动", "campaign"],
    "ad_group": ["广告组", "组", "adgroup", "ad_group"],
    "creative": ["创意", "素材", "creative", "creatives"],
}


# ==================== 内部时间解析类 ====================

@dataclass
class SimpleTimeRange:
    """简单时间范围类"""
    start_date: str
    end_date: str
    unit: str = "day"


def simple_parse_time_range(text: str) -> Optional[SimpleTimeRange]:
    """简单的时间范围解析"""
    today = date.today()
    text_lower = text.lower()

    if "今天" in text_lower:
        return SimpleTimeRange(
            start_date=str(today),
            end_date=str(today),
            unit="day"
        )
    elif "昨天" in text_lower:
        yesterday = today - timedelta(days=1)
        return SimpleTimeRange(
            start_date=str(yesterday),
            end_date=str(yesterday),
            unit="day"
        )
    elif "近7天" in text_lower or "最近7天" in text_lower:
        start = today - timedelta(days=6)
        return SimpleTimeRange(
            start_date=str(start),
            end_date=str(today),
            unit="day"
        )
    elif "近30天" in text_lower or "最近30天" in text_lower:
        start = today - timedelta(days=29)
        return SimpleTimeRange(
            start_date=str(start),
            end_date=str(today),
            unit="day"
        )
    elif "本月" in text_lower:
        first_day = today.replace(day=1)
        return SimpleTimeRange(
            start_date=str(first_day),
            end_date=str(today),
            unit="day"
        )
    elif "上个月" in text_lower:
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        return SimpleTimeRange(
            start_date=str(first_day_last_month),
            end_date=str(last_day_last_month),
            unit="day"
        )
    elif "上周" in text_lower:
        # 上周一到上周日
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        return SimpleTimeRange(
            start_date=str(last_monday),
            end_date=str(last_sunday),
            unit="day"
        )

    # 解析 "4月份" / "四月" / "2026年4月" / "2026年四月份"
    month_pattern = r'(?:(\d{4})[年年])?\s*(\d{1,2})[月份]'
    match = re.search(month_pattern, text_lower)
    if match:
        year = int(match.group(1)) if match.group(1) else today.year
        month = int(match.group(2))
        # Get first day of month
        if month < 1 or month > 12:
            return None
        # First day is always 1
        start_date = date(year, month, 1)
        # Last day is first day of next month - 1 day
        if month == 12:
            next_month_first = date(year + 1, 1, 1)
        else:
            next_month_first = date(year, month + 1, 1)
        end_date = next_month_first - timedelta(days=1)
        return SimpleTimeRange(
            start_date=str(start_date),
            end_date=str(end_date),
            unit="day"
        )

    # 解析 "一月" / "二月" / "三月" etc (中文月份名称)
    cn_month_map = {
        '一月': 1, '二月': 2, '三月': 3, '四月': 4,
        '五月': 5, '六月': 6, '七月': 7, '八月': 8,
        '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,
    }
    for name, num in cn_month_map.items():
        if name in text_lower or (name.replace('月', '月份') in text_lower):
            year = today.year
            start_date = date(year, num, 1)
            if num == 12:
                next_month_first = date(year + 1, 1, 1)
            else:
                next_month_first = date(year, num + 1, 1)
            end_date = next_month_first - timedelta(days=1)
            return SimpleTimeRange(
                start_date=str(start_date),
                end_date=str(end_date),
                unit="day"
            )

    return None


def simple_map_metrics(text: str) -> List[str]:
    """简单的指标映射

    使用正则边界匹配，避免子串误匹配（如"分开展示"中的"展示"不要匹配成指标）
    注意：在 Unicode Python 正则中，中文汉字 isalnum() → True，所以\w包含汉字
    因此我们需要用不同的方式：只要求指标前面不能跟小写字母/阿拉伯数字，避免嵌入到其他词中
    """
    metrics = []
    text_lower = text.lower()

    for alias, standard in METRIC_MAPPING.items():
        alias_lower = alias.lower()
        # Use lookaround assertions that work with Chinese:
        # - 断言前面不是小写字母或数字 → 保证指标不嵌入在其他词中
        # - 断言后面不是小写字母或数字 → 同上
        pattern = r'(?<![a-z0-9])%s(?![a-z0-9])' % re.escape(alias_lower)
        matches = list(re.finditer(pattern, text_lower))
        if matches:
            # Special case: "展示" as verb in "分开展示" - skip this occurrence
            if alias == "展示":
                for match in matches:
                    start = match.start()
                    # Check if "展示" is preceded by "展开" / "开展" (common case "分开展示")
                    if start >= 2:
                        prev_two = text_lower[start-2:start]
                        if prev_two == "展开" or prev_two == "开展":
                            # This is "X开展示", "展示" is a verb, not the metric impression → skip
                            continue
                    # If we get here, accept the match
                    if standard not in metrics:
                        metrics.append(standard)
            else:
                if standard not in metrics:
                    metrics.append(standard)

    # 如果没有识别到指标，返回默认指标
    return metrics if metrics else []


# ==================== 数据类 ====================

@dataclass
class IntentAnalysisResult:
    """意图分析结果"""
    field_context: FieldContext
    missing_fields: List[str]
    analysis_type_hint: Optional[AnalysisType]
    filter_type_hint: Optional[FilterType]
    confidence: float
    raw_extractions: Dict[str, Any]


# ==================== 规则提取器 ====================

class RuleBasedExtractor:
    """基于规则的快速字段提取器"""

    # 广告主 ID 提取模式
    # 更具体的模式放前面，避免被更泛化的模式提前匹配
    # Supports:
    # - Integer IDs: 6, 123
    # - UUIDs: a5972030-c1d3-4d23-bcd2-02c211411ff6
    ADVERTISER_ID_PATTERNS = [
        r'id[为是]\s*([a-f0-9\-]+)\s*的?广告主',
        r'广告主id[为是]\s*([a-f0-9\-]+)',
        r'广告主id\s*[为是]?\s*([a-f0-9\-]+)',
        r'广告主\s*[：:]\s*([a-f0-9\-]+)',
        r'advertiser\s*[=:]\s*([a-f0-9\-]+)',
        r'([a-f0-9\-]{8,}-[a-f0-9\-]+)\s*广告主',
        r'广告主\s*([a-f0-9\-]{8,})',
        # Match standalone UUID (when user just inputs the UUID)
        r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
        # Fallback to integer patterns
        r'id[为是]\s*(\d+)\s*的?广告主',
        r'广告主id[为是]\s*(\d+)',
        r'广告主id\s*[为是]?\s*(\d+)',
        r'广告主\s*[：:]\s*(\d+)',
        r'advertiser\s*[=:]\s*(\d+)',
        r'(\d+)\s*号广告主',
        r'(\d+)\s*广告主',
        r'广告主\s*(\d+)',
    ]

    # 场景关键词
    SCENE_KEYWORDS = {
        AnalysisType.TIME_TREND: [
            '趋势', '变化', '走势', '随时间', '按天', '按周', '按月',
            'trend', 'over time', 'daily', 'weekly', 'monthly'
        ],
        AnalysisType.PERIOD_COMPARISON: [
            '对比', '比较', 'vs', 'versus', '相比', '同期', '环比', '同比'
        ],
        AnalysisType.AUDIENCE_DISTRIBUTION: [
            '分布', '占比', '按性别', '按年龄', '按地区', '按兴趣',
            'distribution', 'breakdown', 'by gender', 'by age'
        ],
        AnalysisType.ENTITY_TABLE: [
            '列表', '排名', 'top', '前', '最高', '最低', '最好', '最差',
            'list', 'rank', 'sort', 'order'
        ],
        AnalysisType.SUMMARY: [
            '概览', '摘要', '总结', '整体', '概况', 'overview', 'summary'
        ]
    }

    # 筛选条件关键词
    FILTER_KEYWORDS = {
        FilterType.WHERE: [
            '等于', '是', '包含', '在...中', '属于', '=', '==', 'in'
        ],
        FilterType.HAVING: [
            '大于', '小于', '超过', '低于', '高于', '>=', '<=', '>', '<',
            '大于等于', '小于等于', '最多', '最少', '最高', '最低'
        ]
    }

    # 受众维度关键词
    AUDIENCE_DIMENSION_KEYWORDS = {
        "audience_gender": ["性别", "男女"],
        "audience_age": ["年龄", "年龄段"],
        "audience_os": ["系统", "平台", "操作系统"],
        "audience_country": ["国家"],
        "audience_city": ["城市", "地区", "地域"],
        "region_id": ["区域"],
        "device_type": ["设备"],
        "industry": ["行业"],
        "audience_interest": ["兴趣", "兴趣标签"]
    }

    def __init__(self):
        self._metric_keywords = self._build_metric_keywords()
        self._level_keywords = self._build_level_keywords()

    def _build_metric_keywords(self) -> Dict[str, str]:
        """构建指标关键词映射"""
        keywords = {}
        for alias, standard in METRIC_MAPPING.items():
            keywords[alias.lower()] = standard
        return keywords

    def _build_level_keywords(self) -> Dict[str, str]:
        """构建层级关键词映射"""
        keywords = {}
        for standard, aliases in AD_LEVEL_MAP.items():
            for alias in aliases:
                keywords[alias.lower()] = standard
        return keywords

    def extract_advertiser_ids(self, text: str) -> List[str]:
        """提取广告主 ID

        Supports both integer IDs and UUID string IDs.
        For integer IDs, keep as string but will convert to int in filter query if possible.
        """
        ids = []
        text_lower = text.lower()

        for pattern in self.ADVERTISER_ID_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                adv_id_str = str(match).strip()
                # Try to convert to integer for proper ES matching (ES has integer field)
                # If fails, keep as string (for UUID)
                try:
                    adv_id_int = int(adv_id_str)
                    # Store as string still because need consistent type for pydantic
                    # But we'll convert to int during query building
                    if str(adv_id_int) not in ids:
                        ids.append(str(adv_id_int))
                except ValueError:
                    if adv_id_str not in ids:
                        ids.append(adv_id_str)

        return ids

    def extract_time_range(self, text: str) -> Optional[AnalysisTimeRange]:
        """提取时间范围"""
        parsed = simple_parse_time_range(text)
        if parsed:
            return AnalysisTimeRange(
                start_date=parsed.start_date,
                end_date=parsed.end_date,
                granularity=parsed.unit
            )
        return None

    def extract_metrics(self, text: str) -> List[str]:
        """提取指标"""
        return simple_map_metrics(text)

    def extract_target_level(self, text: str) -> Optional[str]:
        """提取目标实体层级"""
        text_lower = text.lower()

        for alias, standard in self._level_keywords.items():
            if alias in text_lower:
                return standard

        return None

    def extract_audience_dimension(self, text: str) -> Optional[str]:
        """提取受众维度"""
        text_lower = text.lower()

        for dimension, keywords in self.AUDIENCE_DIMENSION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return dimension

        return None

    def detect_analysis_type(self, text: str) -> Optional[AnalysisType]:
        """检测分析类型（场景识别）"""
        text_lower = text.lower()
        matches = []

        for analysis_type, keywords in self.SCENE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    matches.append((analysis_type, keyword))
                    break  # 每个类型只匹配一次

        if not matches:
            return None

        # 返回第一个匹配到的类型
        return matches[0][0]

    def detect_filter_type(self, text: str) -> Optional[FilterType]:
        """检测筛选类型"""
        text_lower = text.lower()
        has_where = False
        has_having = False

        # 检查 WHERE 类型关键词
        for keyword in self.FILTER_KEYWORDS[FilterType.WHERE]:
            if keyword.lower() in text_lower:
                has_where = True
                break

        # 检查 HAVING 类型关键词
        for keyword in self.FILTER_KEYWORDS[FilterType.HAVING]:
            if keyword.lower() in text_lower:
                has_having = True
                break

        if has_where and has_having:
            return FilterType.MIXED
        elif has_having:
            return FilterType.HAVING
        elif has_where:
            return FilterType.WHERE

        return None

    def calculate_confidence(self, extraction: Dict[str, Any]) -> float:
        """计算提取结果的置信度"""
        score = 0.0
        total = 0.0

        # 广告主 ID
        total += 1.0
        if extraction.get("advertiser_ids"):
            score += 1.0

        # 时间范围
        total += 1.0
        if extraction.get("time_range"):
            score += 1.0

        # 指标
        total += 1.0
        if extraction.get("metrics"):
            score += 1.0

        # 目标层级
        total += 0.5
        if extraction.get("target_level"):
            score += 0.5

        # 分析类型
        total += 0.5
        if extraction.get("analysis_type"):
            score += 0.5

        return score / total if total > 0 else 0.0


# ==================== IntentAnalyzer 主类 ====================

class IntentAnalyzer:
    """
    轻量级意图分析器

    在 CoT 规划之前进行初步的字段提取和场景识别。
    主要使用规则提取，LLM 作为辅助。
    """

    def __init__(self):
        self.rule_extractor = RuleBasedExtractor()

    def analyze(
        self,
        user_input: str,
        conversation_history: List[Dict[str, Any]] = None
    ) -> IntentAnalysisResult:
        """
        分析用户输入，提取字段和识别场景

        Args:
            user_input: 用户输入文本
            conversation_history: 对话历史（用于上下文继承）

        Returns:
            IntentAnalysisResult: 分析结果
        """
        raw_extractions = {}

        # 1. 规则提取（主要方法）
        raw_extractions["advertiser_ids"] = self.rule_extractor.extract_advertiser_ids(user_input)
        raw_extractions["time_range"] = self.rule_extractor.extract_time_range(user_input)
        raw_extractions["metrics"] = self.rule_extractor.extract_metrics(user_input)
        raw_extractions["target_level"] = self.rule_extractor.extract_target_level(user_input)
        raw_extractions["audience_dimension"] = self.rule_extractor.extract_audience_dimension(user_input)
        raw_extractions["analysis_type"] = self.rule_extractor.detect_analysis_type(user_input)
        raw_extractions["filter_type"] = self.rule_extractor.detect_filter_type(user_input)

        # 2. 从对话历史继承上下文
        if conversation_history:
            self._apply_context_inheritance(raw_extractions, conversation_history)

        # 3. 构建 FieldContext
        field_context = self._build_field_context(raw_extractions)

        # 4. 识别缺失字段
        missing_fields = self._identify_missing_fields(field_context)

        # 5. 计算置信度
        confidence = self.rule_extractor.calculate_confidence(raw_extractions)

        # 6. 确定场景提示
        analysis_type_hint = raw_extractions.get("analysis_type")
        filter_type_hint = raw_extractions.get("filter_type")

        # 默认场景提示
        if analysis_type_hint is None:
            if field_context.metrics and len(field_context.metrics) > 0:
                analysis_type_hint = AnalysisType.SUMMARY

        return IntentAnalysisResult(
            field_context=field_context,
            missing_fields=missing_fields,
            analysis_type_hint=analysis_type_hint,
            filter_type_hint=filter_type_hint,
            confidence=confidence,
            raw_extractions=raw_extractions
        )

    def _apply_context_inheritance(
        self,
        extractions: Dict[str, Any],
        conversation_history: List[Dict[str, Any]]
    ):
        """从对话历史继承上下文"""
        # 从最近的消息中提取可能的上下文
        recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history

        for msg in reversed(recent_messages):
            content = str(msg.get("content", ""))

            # 继承广告主 ID（如果当前没有）
            if not extractions.get("advertiser_ids"):
                ids = self.rule_extractor.extract_advertiser_ids(content)
                if ids:
                    extractions["advertiser_ids"] = ids
                    logger.debug(f"Inherited advertiser_ids: {ids}")

            # 继承时间范围（如果当前没有）
            if not extractions.get("time_range"):
                time_range = self.rule_extractor.extract_time_range(content)
                if time_range:
                    extractions["time_range"] = time_range
                    logger.debug(f"Inherited time_range: {time_range}")

            # 如果已经提取到关键信息，停止继承
            if extractions.get("advertiser_ids") and extractions.get("time_range"):
                break

    def _build_field_context(self, extractions: Dict[str, Any]) -> FieldContext:
        """构建 FieldContext 对象"""
        advertiser_ids = extractions.get("advertiser_ids")
        time_range = extractions.get("time_range")
        target_level = extractions.get("target_level")
        metrics = extractions.get("metrics")
        audience_dimension = extractions.get("audience_dimension")

        return FieldContext(
            advertiser_ids=advertiser_ids if advertiser_ids is not None else None,
            time_range=time_range,
            target_level=target_level,
            metrics=metrics if metrics is not None else None,
            audience_dimension=audience_dimension,
            compare_time_range=None,  # 这个在 CoT 阶段处理
            entity_ids=None,
            additional_fields={}
        )

    def _identify_missing_fields(self, field_context: FieldContext) -> List[str]:
        """识别缺失的必要字段"""
        missing = []

        # 广告主 ID 通常是必要的
        if not field_context.advertiser_ids:
            missing.append("advertiser_ids")

        # 时间范围通常是必要的
        if not field_context.time_range:
            missing.append("time_range")

        # 指标通常是必要的
        if not field_context.metrics:
            missing.append("metrics")

        return missing


# ==================== 便捷函数 ====================

def create_intent_analyzer() -> IntentAnalyzer:
    """创建 IntentAnalyzer 实例（工厂函数）"""
    return IntentAnalyzer()
