from typing import List, Dict, Any, Literal, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .config import OPENAI_API_KEY, ARK_BASE_URL, ARK_API_KEY, ARK_LLM_MODEL
from .database import get_db_session
from .retriever import RagRetriever, RetrievalResult


# 单例缓存
_llm_instance: ChatOpenAI = None
_rag_generator_instance: 'RagAnswerGenerator' = None


def _get_llm():
    """获取 LLM 单例 - 优先使用火山引擎 Ark"""
    global _llm_instance
    if _llm_instance is None:
        if ARK_LLM_MODEL and ARK_API_KEY:
            _llm_instance = ChatOpenAI(
                model=ARK_LLM_MODEL,
                api_key=ARK_API_KEY,
                base_url=ARK_BASE_URL,
                temperature=0,
            )
        else:
            _llm_instance = ChatOpenAI(
                model="gpt-3.5-turbo",
                api_key=OPENAI_API_KEY,
                temperature=0,
            )
    return _llm_instance


def get_rag_generator() -> 'RagAnswerGenerator':
    """获取 RagAnswerGenerator 单例（避免每次重新初始化）"""
    global _rag_generator_instance
    if _rag_generator_instance is None:
        _rag_generator_instance = RagAnswerGenerator()
    return _rag_generator_instance


# 关键词路由：先快速判断，大部分问题不走 LLM
REPORT_KEYWORDS = ["数据", "报表", "曝光", "点击", "转化", "消耗", "成本",
                   "趋势", "分析", "对比", "统计", "查询", "多少", "昨日",
                   "上周", "上月", "今天", "昨天", "本周", "本月", "周", "月", "日"]


class IntentRouter:
    """意图路由 - 判断用户问题走报表还是 RAG"""

    def classify(self, user_input: str) -> Literal["report", "knowledge"]:
        """分类用户意图 - 纯关键词匹配，极速响应"""
        if any(k in user_input for k in REPORT_KEYWORDS):
            return "report"
        return "knowledge"


class RagAnswerGenerator:
    """RAG 回答生成器"""

    SYSTEM_PROMPT = """You are a professional advertising knowledge assistant. Answer user questions based on the provided reference documents clearly and professionally.

Rules:
1. Answer based only on the content in the reference documents
2. If the reference documents have relevant content, summarize and answer directly in Chinese
3. Only say "Sorry, no relevant information" if documents have ZERO related content
4. Be concise, structured, and easy to understand

Reference documents:
{context}"""

    # 兜底回答模板
    FALLBACK_ANSWER = """抱歉，目前的知识库中没有找到与「{query}」相关的内容。

您可以尝试：
1. 换一种问法，使用更通用的关键词
2. 查看以下常见问题，也许有您需要的："""

    # 常见问题建议
    COMMON_SUGGESTIONS = [
        "什么是 CTR？",
        "什么是 CPA？",
        "怎么优化广告效果？",
        "冷启动跑不动怎么办？",
        "A/B 测试怎么做？",
    ]

    def __init__(self):
        # Top 3 足够回答，检索更快
        self.retriever = RagRetriever(retrieve_top_k=3)

    def _build_context(self, retrieval_results: List[RetrievalResult]) -> str:
        """构建上下文字符串"""
        context_parts = []
        for i, result in enumerate(retrieval_results, 1):
            context_parts.append(f"[{i}] {result.content}")
        return "\n\n".join(context_parts)

    def _extract_sources(self, results: List[RetrievalResult]) -> List[str]:
        """提取参考来源（去重）"""
        titles = []
        seen = set()
        for r in results:
            if r.title and r.title not in seen:
                titles.append(r.title)
                seen.add(r.title)
        return titles

    def _generate_query_suggestions(self, query: str, results: List[RetrievalResult]) -> List[str]:
        """快速生成相关问题（直接取通用建议，性能优先）"""
        return self.COMMON_SUGGESTIONS[:3]

    def _format_answer(self, answer: str, sources: List[str], suggestions: List[str], show_sources: bool = True) -> str:
        """格式化回答，添加来源和建议"""
        result_parts = [answer]

        # 添加参考来源（兜底回答时不显示）
        if show_sources and sources:
            source_str = "、".join([f"《{s}》" for s in sources])
            result_parts.append(f"\n\n📚 参考来源：{source_str}")

        # 添加相关问题建议
        if suggestions:
            result_parts.append(f"\n💡 你可能还想问：{'、'.join(suggestions[:3])}")

        return "\n".join(result_parts)

    def retrieve_with_results(self, query: str) -> List[RetrievalResult]:
        """检索并返回完整的结果对象"""
        db_session = get_db_session()
        try:
            return self.retriever.search(query, db_session)
        finally:
            db_session.close()

    def retrieve_context(self, query: str) -> List[str]:
        """检索相关上下文（仅返回内容字符串，向后兼容）"""
        results = self.retrieve_with_results(query)
        return [r.content for r in results]

    def generate(self, query: str, context: List[str] = None) -> str:
        """生成回答"""
        # 获取完整的检索结果
        if context is None:
            results = self.retrieve_with_results(query)
        else:
            # 如果只传入了字符串列表，构造临时的 RetrievalResult 对象
            results = [
                RetrievalResult(
                    chunk_id=f"temp_{i}",
                    doc_id="temp",
                    content=c,
                    score=1.0,
                    title=None
                )
                for i, c in enumerate(context)
            ]

        # 相关性阈值：向量相似度 + 关键词匹配双重判断
        # 本地 embedding 对无意义查询的分数判断不够准确，需要更严格
        VECTOR_THRESHOLD = 0.80  # 向量相似度阈值，提高到0.8
        has_relevant = False
        if results:
            top_score = results[0].score
            # 严格的关键词匹配：查询中必须包含关键词
            keywords = ['CTR', 'CPA', 'CPC', 'CPM', 'ROI', 'ARPU',
                       '点击率', '转化率', '点击成本', '千次展示',
                       '冷启动', '素材', '创意', '落地页', '定向',
                       '出价', '竞价', '预算', '消耗', '优化', 'A/B',
                       '测试', '广告', '投放', '转化', '成本', '效果',
                       '归因', '留存', 'LTV', '生命周期', '衰退',
                       '账户', '余额', '充值', '续费', '支付', '资金',
                       '发票', '财务', '对账', 'ctr', 'cpa', 'roi']
            query_clean = query.replace('？', '').replace('?', '').replace('。', '')
            has_keyword_match = any(k.lower() in query_clean.lower() for k in keywords)
            # 两个条件满足一个即可
            has_relevant = top_score >= VECTOR_THRESHOLD or has_keyword_match

        # 兜底回答
        if not has_relevant or not results:
            fallback = self.FALLBACK_ANSWER.format(query=query)
            fallback += "\n  - " + "\n  - ".join(self.COMMON_SUGGESTIONS[:4])
            # 兜底回答只显示建议，不显示来源
            return self._format_answer(fallback, [], self.COMMON_SUGGESTIONS[:4], show_sources=False)

        # 构建上下文
        context_str = self._build_context(results)

        try:
            # 创建新的 LLM 实例并调用
            llm = _get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.SYSTEM_PROMPT.format(context=context_str)),
                ("human", f"用户问题: {query}"),
            ])

            chain = prompt | llm
            response = chain.invoke({"query": query})
            answer = response.content.strip()

            # 检测 LLM 是否自己返回了兜底回答
            llm_fallback = "抱歉，目前的知识库中没有" in answer
        except Exception:
            # LLM 调用失败时直接返回检索到的文档摘要
            answer = ""
            for i, r in enumerate(results[:3], 1):
                answer += f"### {r.title}\n{r.content}\n\n"
            llm_fallback = False

        # 提取来源和建议
        sources = self._extract_sources(results)
        suggestions = self._generate_query_suggestions(query, results)

        # 格式化返回（LLM 自己兜底时不显示来源）
        return self._format_answer(answer, sources, suggestions, show_sources=not llm_fallback)


# LangGraph 节点函数
def intent_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """意图路由节点"""
    user_input = state.get("user_input", "")
    router = IntentRouter()
    query_type = router.classify(user_input)
    return {"query_type": query_type}


def rag_retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """RAG 检索节点（向后兼容）"""
    query = state.get("user_input", "")
    generator = RagAnswerGenerator()
    context = generator.retrieve_context(query)
    return {"rag_context": context}


def rag_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """RAG 回答生成节点"""
    query = state.get("user_input", "")
    generator = RagAnswerGenerator()

    # 直接检索完整结果（包含来源信息），不依赖 rag_context
    # 这样可以保留完整的文档标题、分数等元数据
    answer = generator.generate(query)

    # 构建 final_report 格式以统一输出
    final_report = {
        "title": "知识库查询结果",
        "time_range": {"start": "", "end": ""},
        "metrics": [],
        "highlights": [
            {"type": "info", "text": answer}
        ],
        "data_table": {
            "columns": [],
            "rows": []
        },
        "next_queries": []
    }

    return {"rag_answer": answer, "final_report": final_report}
