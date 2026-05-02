from typing import List, Dict, Any, Literal, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .config import OPENAI_API_KEY
from .database import get_db_session
from .retriever import RagRetriever


class IntentRouter:
    """意图路由 - 判断用户问题走报表还是 RAG"""

    SYSTEM_PROMPT = """你是一个智能路由助手，根据用户问题判断应该走哪个分支：

- 如果用户想看数据、报表、图表、趋势、对比、分析某个指标、查某个维度、筛选某个条件 → 返回 "report"
- 如果用户问概念、术语、使用方法、帮助、说明、定义、解释是什么、方法论、最佳实践 → 返回 "knowledge"

请只返回一个单词：report 或 knowledge，不要返回任何其他内容。"""

    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )

    def classify(self, user_input: str) -> Literal["report", "knowledge"]:
        """分类用户意图"""
        messages = [
            ("system", self.SYSTEM_PROMPT),
            ("human", f"用户问题: {user_input}"),
        ]
        response = self.llm.invoke(messages)
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
1. 只基于参考文档中的内容回答，不要编造信息
2. 如果参考文档中没有相关内容，说明"抱歉，目前的知识库中没有相关信息"
3. 回答要条理清晰，重点突出
4. 专业术语可以适当解释
5. 用中文回答

参考文档：
{context}"""

    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=OPENAI_API_KEY,
            temperature=0.3,
        )
        self.retriever = RagRetriever()

    def _build_context(self, retrieval_results: List) -> str:
        """构建上下文字符串"""
        context_parts = []
        for i, result in enumerate(retrieval_results, 1):
            context_parts.append(f"[{i}] {result.content}")
        return "\n\n".join(context_parts)

    def retrieve_context(self, query: str) -> List[str]:
        """检索相关上下文"""
        db_session = get_db_session()
        try:
            results = self.retriever.search(query, db_session)
            return [r.content for r in results]
        finally:
            db_session.close()

    def generate(self, query: str, context: List[str] = None) -> str:
        """生成回答"""
        if context is None:
            context = self.retrieve_context(query)

        if not context:
            return "抱歉，暂时没有找到相关帮助文档，您可以试试其他问题。"

        context_str = self._build_context(
            [type("Result", (), {"content": c}) for c in context]
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT.format(context=context_str)),
            ("human", f"用户问题: {query}"),
        ])

        chain = prompt | self.llm
        response = chain.invoke({"query": query})
        return response.content.strip()


# LangGraph 节点函数
def intent_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """意图路由节点"""
    user_input = state.get("user_input", "")
    router = IntentRouter()
    query_type = router.classify(user_input)
    return {"query_type": query_type}


def rag_retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """RAG 检索节点"""
    query = state.get("user_input", "")
    generator = RagAnswerGenerator()
    context = generator.retrieve_context(query)
    return {"rag_context": context}


def rag_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """RAG 回答生成节点"""
    query = state.get("user_input", "")
    context = state.get("rag_context", [])
    generator = RagAnswerGenerator()
    answer = generator.generate(query, context)

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
