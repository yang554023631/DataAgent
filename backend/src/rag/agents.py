from typing import List, Dict, Any, Literal, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .config import OPENAI_API_KEY, ARK_BASE_URL, ARK_API_KEY, ARK_LLM_MODEL
from .database import get_db_session
from .retriever import RagRetriever, RetrievalResult


def _get_llm():
    """获取 LLM 实例 - 优先使用火山引擎 Ark"""
    if ARK_LLM_MODEL and ARK_API_KEY:
        return ChatOpenAI(
            model=ARK_LLM_MODEL,
            api_key=ARK_API_KEY,
            base_url=ARK_BASE_URL,
            temperature=0,
        )
    return ChatOpenAI(
        model="gpt-3.5-turbo",
        api_key=OPENAI_API_KEY,
        temperature=0,
    )


class IntentRouter:
    """意图路由 - 判断用户问题走报表还是 RAG"""

    SYSTEM_PROMPT = """你是一个智能路由助手，根据用户问题判断应该走哪个分支：

- 如果用户想看数据、报表、图表、趋势、对比、分析某个指标、查某个维度、筛选某个条件 → 返回 "report"
- 如果用户问概念、术语、使用方法、帮助、说明、定义、解释是什么、方法论、最佳实践 → 返回 "knowledge"

请只返回一个单词：report 或 knowledge，不要返回任何其他内容。"""

    def classify(self, user_input: str) -> Literal["report", "knowledge"]:
        """分类用户意图"""
        # 每次调用都创建新的 LLM 实例，避免 tokenizers forking 导致的问题
        llm = _get_llm()
        messages = [
            ("system", self.SYSTEM_PROMPT),
            ("human", f"用户问题: {user_input}"),
        ]
        response = llm.invoke(messages)
        result = response.content.strip().lower()

        # 确保返回值合法
        if result not in ["report", "knowledge"]:
            # 默认走 knowledge
            return "knowledge"
        return result


class RagAnswerGenerator:
    """RAG 回答生成器"""

    SYSTEM_PROMPT = """你是一个广告行业的专业知识助手。请基于提供的参考文档，用简洁、专业、易懂的语言回答用户问题。

回答要求：
1. 基于参考文档中的内容回答，不要编造文档中没有的信息
2. 如果参考文档中有相关内容，请完整、准确地回答问题
3. 只有当参考文档中完全没有相关内容时，才说明"抱歉，目前的知识库中没有相关信息"
4. 回答要条理清晰，重点突出
5. 专业术语可以适当解释
6. 用中文回答

参考文档：
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
        self.retriever = RagRetriever()

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
        """基于检索结果生成相关问题建议"""
        # 如果有相关结果，从文档标题中提取建议
        if results:
            # 简单的基于检索结果的建议
            sources = self._extract_sources(results)
            suggestions = []
            for source in sources[:3]:
                # 从文档标题生成建议问题
                if "CTR" in source or "点击率" in source:
                    suggestions.append("怎么提升 CTR？")
                elif "CPA" in source or "转化成本" in source:
                    suggestions.append("怎么降低 CPA？")
                elif "冷启动" in source:
                    suggestions.append("冷启动需要多久？")
                elif "A/B" in source or "测试" in source:
                    suggestions.append("A/B测试需要注意什么？")
                elif "素材" in source:
                    suggestions.append("素材怎么优化？")
                elif "落地页" in source:
                    suggestions.append("落地页有什么优化技巧？")
                elif "定向" in source:
                    suggestions.append("广告怎么定向？")

            # 补充通用建议
            suggestions.extend(self.COMMON_SUGGESTIONS[:2])
            return suggestions[:4]

        # 没有结果时返回通用建议
        return self.COMMON_SUGGESTIONS

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

        # 注意：检索过程中 CrossEncoder 的 forking 行为可能影响 self.llm 的状态
        # 所以每次调用 LLM 前都创建一个新的 LLM 实例
        llm = _get_llm()

        # 调用 LLM 生成回答
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT.format(context=context_str)),
            ("human", f"用户问题: {query}"),
        ])

        chain = prompt | llm
        response = chain.invoke({"query": query})
        answer = response.content.strip()

        # 检测 LLM 是否自己返回了兜底回答
        llm_fallback = "抱歉，目前的知识库中没有" in answer

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
