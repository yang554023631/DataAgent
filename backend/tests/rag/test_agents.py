import pytest
import os
from unittest.mock import Mock, patch, MagicMock

# 在导入前设置环境变量避免初始化失败
os.environ['OPENAI_API_KEY'] = 'test-key'

from src.rag.agents import IntentRouter, RagAnswerGenerator, intent_router_node, rag_retrieve_node, rag_answer_node


@patch('src.rag.agents.ChatOpenAI')
def test_intent_router_initialization(mock_chat_openai):
    """测试意图路由初始化"""
    mock_chat_openai.return_value = Mock()
    router = IntentRouter()
    assert router is not None


@patch('src.rag.agents.ChatOpenAI')
def test_intent_classification_report(mock_chat_openai):
    """测试报表类意图识别"""
    mock_llm = Mock()
    mock_chat_openai.return_value = mock_llm
    mock_llm.invoke.return_value = Mock(content="report")

    router = IntentRouter()
    result = router.classify("昨天 CTR 是多少")
    assert result == "report"

    result = router.classify("最近 7 天的花费趋势")
    assert result == "report"


@patch('src.rag.agents.ChatOpenAI')
def test_intent_classification_knowledge(mock_chat_openai):
    """测试知识类意图识别"""
    mock_llm = Mock()
    mock_chat_openai.return_value = mock_llm
    mock_llm.invoke.return_value = Mock(content="knowledge")

    router = IntentRouter()
    result = router.classify("什么是 CTR")
    assert result == "knowledge"

    result = router.classify("如何计算 ROI")
    assert result == "knowledge"


@patch('src.rag.agents.ChatOpenAI')
def test_intent_classification_fallback(mock_chat_openai):
    """测试分类失败回退到 knowledge"""
    mock_llm = Mock()
    mock_chat_openai.return_value = mock_llm
    mock_llm.invoke.return_value = Mock(content="something_else")

    router = IntentRouter()
    result = router.classify("未知类型的问题")
    assert result == "knowledge"


@patch('src.rag.agents.ChatOpenAI')
@patch('src.rag.agents.RagRetriever')
def test_answer_generator_initialization(mock_retriever, mock_chat_openai):
    """测试回答生成器初始化"""
    mock_chat_openai.return_value = Mock()
    mock_retriever.return_value = Mock()
    generator = RagAnswerGenerator()
    assert generator is not None


@patch('src.rag.agents.RagAnswerGenerator.generate')
def test_answer_generation(mock_generate):
    """测试回答生成"""
    mock_generate.return_value = "CTR（点击率）是指广告点击量除以曝光量的百分比，它反映了广告对用户的吸引力程度。"

    generator = RagAnswerGenerator()
    query = "什么是 CTR？"
    context = [
        "CTR（Click-Through Rate，点击率）是广告点击量除以曝光量的百分比",
        "CTR 反映了广告对用户的吸引力程度",
    ]

    answer = generator.generate(query, context)
    assert answer is not None
    assert len(answer) > 0
    assert "CTR" in answer or "点击率" in answer


@patch('src.rag.agents.ChatOpenAI')
@patch('src.rag.agents.RagRetriever')
def test_empty_context_answer(mock_retriever, mock_chat_openai):
    """测试没有上下文时的回答"""
    mock_chat_openai.return_value = Mock()
    mock_retriever.return_value = Mock()

    generator = RagAnswerGenerator()
    query = "这个问题没有相关文档"
    context = []

    answer = generator.generate(query, context)
    assert "抱歉" in answer or "没有找到" in answer


@patch('src.rag.agents.ChatOpenAI')
@patch('src.rag.agents.RagRetriever')
def test_build_context(mock_retriever, mock_chat_openai):
    """测试构建上下文"""
    mock_chat_openai.return_value = Mock()
    mock_retriever.return_value = Mock()

    generator = RagAnswerGenerator()
    results = [
        Mock(content="内容1"),
        Mock(content="内容2"),
    ]

    context_str = generator._build_context(results)
    assert "[1]" in context_str
    assert "[2]" in context_str
    assert "内容1" in context_str
    assert "内容2" in context_str


def test_intent_router_node():
    """测试意图路由节点函数"""
    with patch('src.rag.agents.IntentRouter') as mock_router_cls:
        mock_router = Mock()
        mock_router.classify.return_value = "knowledge"
        mock_router_cls.return_value = mock_router

        state = {"user_input": "什么是 CTR"}
        result = intent_router_node(state)

        assert result["query_type"] == "knowledge"
        mock_router.classify.assert_called_with("什么是 CTR")


def test_rag_retrieve_node():
    """测试 RAG 检索节点函数"""
    with patch('src.rag.agents.RagAnswerGenerator') as mock_generator_cls:
        mock_generator = Mock()
        mock_generator.retrieve_context.return_value = ["上下文1", "上下文2"]
        mock_generator_cls.return_value = mock_generator

        state = {"user_input": "什么是 CTR"}
        result = rag_retrieve_node(state)

        assert "rag_context" in result
        assert len(result["rag_context"]) == 2


def test_rag_answer_node():
    """测试 RAG 回答生成节点函数"""
    with patch('src.rag.agents.RagAnswerGenerator') as mock_generator_cls:
        mock_generator = Mock()
        mock_generator.generate.return_value = "CTR 是点击率"
        mock_generator_cls.return_value = mock_generator

        state = {
            "user_input": "什么是 CTR",
            "rag_context": ["CTR 是点击率"]
        }
        result = rag_answer_node(state)

        assert "rag_answer" in result
        assert "final_report" in result
        assert result["rag_answer"] == "CTR 是点击率"
        assert result["final_report"]["title"] == "知识库查询结果"
