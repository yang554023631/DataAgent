"""
顶层意图分类器

混合策略：规则快筛 + LLM 精分
- 明确的报表查询 → 规则快筛直接放行（毫秒级）
- 不确定的 → LLM 做三分类（report / knowledge / out_of_domain）+ 置信度
"""
import json
import logging
import re
from typing import Optional, List

from src.intent.llm_client import get_intent_llm_client, IntentLLMClient
from src.intent.prompts import TOP_CLASSIFIER_SYSTEM_PROMPT
from src.intent.models import TopClassificationResult

logger = logging.getLogger(__name__)

# 置信度阈值（低于此值触发澄清）
CONFIDENCE_THRESHOLD = 0.7


# ========== 规则快筛关键词 ==========

# 时间关键词
_TIME_KEYWORDS = [
    "今天", "昨天", "前天", "今日", "昨日",
    "本周", "上周", "这周", "上上周",
    "本月", "上个月", "上月", "这个月",
    "近7天", "最近7天", "近30天", "最近30天",
    "近3个月", "最近三个月", "近一个月",
    "日", "周", "月",  # 这些太泛，需要组合判断
]

# 指标关键词（中文 + 英文缩写）
_METRIC_KEYWORDS = [
    "曝光", "点击", "消耗", "转化", "成本", "花费",
    "点击率", "转化率", "投产比",
    "ctr", "cvr", "roi", "cpc", "cpm", "cpa",
    "impression", "click", "conversion",
    "覆盖", "触达", "频次",
]

# 报表查询动作词
_QUERY_ACTION_KEYWORDS = [
    "查看", "查询", "看看", "分析", "统计",
    "报表", "数据", "趋势", "对比",
    "哪些", "多少", "排名", "TOP", "top",
]

# 广告主查询关键词（列表查询、名称查ID、ID查名称）
_ADVERTISER_LOOKUP_KEYWORDS = [
    "广告主列表", "广告主有哪些", "有哪些广告主", "所有广告主",
    "全部广告主", "可用的广告主", "广告主名单",
    "广告主id", "广告主ID", "广告主名称", "广告主名字",
]

# 对比模式正则
_COMPARISON_PATTERNS = [
    re.compile(r'\d+月\s*(vs|VS|和|与)\s*\d+月'),
    re.compile(r'(今天|昨天|本周|上周|本月|上个月)\s*(vs|VS|和|与)\s*(今天|昨天|本周|上周|本月|上个月)'),
]


def _has_advertiser_lookup(text: str) -> bool:
    """检查是否为广告主查询（列表/查ID/查名称）"""
    for kw in _ADVERTISER_LOOKUP_KEYWORDS:
        if kw in text:
            return True
    # "XX 广告主" + "叫什么" / "ID是多少"
    if "广告主" in text and ("叫什么" in text or "是什么" in text or "ID" in text or "id" in text or "名称" in text):
        return True
    return False


def _has_time_keyword(text: str) -> bool:
    """检查是否包含明确的时间关键词（排除单个字的情况）"""
    for kw in _TIME_KEYWORDS:
        if len(kw) >= 2 and kw in text:
            return True
    return False


def _has_metric_keyword(text: str) -> bool:
    """检查是否包含指标关键词（不区分大小写）"""
    text_lower = text.lower()
    for kw in _METRIC_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


def _has_query_action(text: str) -> bool:
    """检查是否包含查询动作词"""
    for kw in _QUERY_ACTION_KEYWORDS:
        if kw in text:
            return True
    return False


def _has_comparison_pattern(text: str) -> bool:
    """检查是否包含明确的对比模式"""
    for pattern in _COMPARISON_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ========== 分类器类 ==========

class IntentTopClassifier:
    """
    顶层意图分类器

    用法:
        classifier = IntentTopClassifier()
        result = await classifier.classify("用户输入")
        print(result.category, result.confidence)
    """

    def __init__(self, llm_client: Optional[IntentLLMClient] = None):
        self._llm_client = llm_client
        self.confidence_threshold = CONFIDENCE_THRESHOLD

    @property
    def llm_client(self) -> IntentLLMClient:
        if self._llm_client is None:
            self._llm_client = get_intent_llm_client()
        return self._llm_client

    # ---- 规则快筛 ----

    def _rule_fastpath(self, user_input: str) -> Optional[TopClassificationResult]:
        """
        规则快筛：只判断"确定是报表"的情况，其他都返回 None 交给 LLM

        命中条件（满足任一条）：
        1. 时间词 + 指标词 同时出现
        2. 查询动作词 + 指标词 同时出现
        3. 明确的对比模式
        """
        has_time = _has_time_keyword(user_input)
        has_metric = _has_metric_keyword(user_input)
        has_action = _has_query_action(user_input)
        has_comparison = _has_comparison_pattern(user_input)
        has_advertiser_lookup = _has_advertiser_lookup(user_input)

        if (has_time and has_metric) or (has_action and has_metric) or (has_comparison and has_metric) or has_advertiser_lookup:
            result = TopClassificationResult(
                category="report",
                confidence=1.0,
                reason="规则快筛：命中报表关键词组合",
                source="rule_fastpath",
            )
            logger.info(f"意图快筛命中: input='{user_input[:50]}...', result=report")
            return result

        return None

    # ---- LLM 分类 ----

    async def _llm_classify(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
    ) -> TopClassificationResult:
        """
        LLM 三分类：report / knowledge / out_of_domain
        """
        # 构建用户提示词
        history_text = ""
        if conversation_history:
            # 取最近 3 轮
            recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            history_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:100]
                history_lines.append(f"{role}: {content}")
            history_text = "\n对话历史:\n" + "\n".join(history_lines)

        user_prompt = f"用户输入：{user_input}{history_text}"

        try:
            response_text = await self.llm_client.call(
                system_prompt=TOP_CLASSIFIER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True,
            )
            data = json.loads(response_text)

            result = TopClassificationResult(
                category=data.get("category", "knowledge"),
                confidence=float(data.get("confidence", 0.5)),
                reason=data.get("reason", ""),
                source="llm",
            )

            logger.info(
                f"意图分类(LLM): category={result.category}, "
                f"confidence={result.confidence:.2f}, "
                f"reason='{result.reason}'"
            )
            return result

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"LLM 分类结果解析失败: {e}, 原始响应前100字: {response_text[:100] if 'response_text' in locals() else 'N/A'}")
            # 解析失败 → 默认 knowledge + 低置信度，触发澄清
            return TopClassificationResult(
                category="knowledge",
                confidence=0.3,
                reason=f"LLM 响应解析失败: {str(e)}",
                source="llm_parse_error",
            )

        except Exception as e:
            logger.error(f"LLM 分类调用失败（已重试仍失败）: {e}")
            # LLM 完全失败 → 降级为 knowledge + 低置信度
            return TopClassificationResult(
                category="knowledge",
                confidence=0.2,
                reason="LLM 服务不可用，降级处理",
                source="llm_failure",
            )

    # ---- 主入口 ----

    async def classify(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
    ) -> TopClassificationResult:
        """
        分类用户意图

        Args:
            user_input: 用户输入文本
            conversation_history: 对话历史列表

        Returns:
            TopClassificationResult
        """
        if not user_input or not user_input.strip():
            return TopClassificationResult(
                category="out_of_domain",
                confidence=0.9,
                reason="空输入",
                source="rule_fastpath",
            )

        # Step 1: 规则快筛
        fast_result = self._rule_fastpath(user_input)
        if fast_result is not None:
            return fast_result

        # Step 2: LLM 精分
        result = await self._llm_classify(user_input, conversation_history)
        return result


# 单例
_top_classifier_instance: Optional[IntentTopClassifier] = None


def get_top_classifier() -> IntentTopClassifier:
    """获取顶层分类器单例"""
    global _top_classifier_instance
    if _top_classifier_instance is None:
        _top_classifier_instance = IntentTopClassifier()
    return _top_classifier_instance
