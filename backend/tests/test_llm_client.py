import pytest
from langchain_openai import ChatOpenAI
from src.intent.llm_client import get_intent_llm_client, IntentLLMClient


class TestIntentLLMClient:
    def test_singleton_instance(self):
        """测试单例模式返回同一个实例"""
        client1 = get_intent_llm_client()
        client2 = get_intent_llm_client()
        assert client1 is client2, "get_intent_llm_client should return the same instance every time"

    def test_client_has_invoke_method(self):
        """测试客户端有 invoke 方法"""
        client = get_intent_llm_client()
        assert hasattr(client, "invoke"), "IntentLLMClient should have invoke method"
        assert callable(client.invoke), "invoke should be callable"

    @pytest.mark.asyncio
    async def test_client_has_ainvoke_method(self):
        """测试客户端有 ainvoke 异步方法"""
        client = get_intent_llm_client()
        assert hasattr(client, "ainvoke"), "IntentLLMClient should have ainvoke method"
        assert callable(client.ainvoke), "ainvoke should be callable"

    def test_llm_configuration(self):
        """测试 LLM 实例配置正确"""
        client = get_intent_llm_client()
        assert hasattr(client, "llm"), "IntentLLMClient should have llm attribute"
        assert isinstance(client.llm, ChatOpenAI), "llm should be ChatOpenAI instance"


if __name__ == "__main__":
    pytest.main([__file__])