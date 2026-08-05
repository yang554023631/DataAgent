import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.llm_client import IntentLLMClient, get_intent_llm_client, get_fallback_classifier


def test_singleton_instance():
    """测试单例模式返回同一个实例"""
    client1 = get_intent_llm_client()
    client2 = get_intent_llm_client()
    assert client1 is client2, "get_intent_llm_client should return the same instance every time"


def test_client_has_call_method():
    """测试客户端有 call 方法"""
    client = get_intent_llm_client()
    assert hasattr(client, "call"), "IntentLLMClient should have call method"
    assert callable(client.call), "call should be callable"


def test_get_fallback_classifier():
    """测试 get_fallback_classifier 函数存在并返回 None"""
    fallback = get_fallback_classifier()
    assert fallback is None, "get_fallback_classifier should return None initially"


@pytest.mark.asyncio
async def test_call_success():
    """测试LLM调用成功"""
    # 创建模拟LLM
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "test response"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    # 创建客户端
    client = IntentLLMClient(llm=mock_llm)

    # 调用方法
    with patch('src.intent.llm_client.ChatPromptTemplate'):
        result = await client.call("system prompt", "user prompt")
        assert result == "test response"


@pytest.mark.asyncio
async def test_call_retry():
    """测试LLM调用重试逻辑"""
    # 创建模拟LLM，前两次失败第三次成功
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "success response"

    call_count = 0
    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count +=1
        if call_count <3:
            raise Exception("API Error")
        return mock_response

    mock_llm.ainvoke = AsyncMock(side_effect=side_effect)

    # 创建客户端，最大重试3次
    client = IntentLLMClient(llm=mock_llm, max_retries=3)

    # 调用方法
    with patch('src.intent.llm_client.ChatPromptTemplate'):
        result = await client.call("system", "user")
        assert result == "success response"
        assert call_count ==3


@pytest.mark.asyncio
async def test_call_llm_all_fail():
    """测试所有重试都失败的情况"""
    # 创建模拟LLM
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))

    # 创建客户端
    client = IntentLLMClient(llm=mock_llm)

    # 验证抛出异常
    with patch('src.intent.llm_client.ChatPromptTemplate'), pytest.raises(Exception):
        await client.call("system", "user")


@pytest.mark.asyncio
async def test_call_json_mode_parameter():
    """测试json_mode参数可以正常工作"""
    # 只测试参数是否存在，不实际调用LLM
    client = get_intent_llm_client()
    # 调用call方法并传入json_mode参数，确保不会抛出异常
    # 我们不需要实际等待响应，只需要验证参数签名正确
    import inspect
    sig = inspect.signature(client.call)
    assert 'json_mode' in sig.parameters
    assert sig.parameters['json_mode'].default == True


if __name__ == "__main__":
    pytest.main([__file__])