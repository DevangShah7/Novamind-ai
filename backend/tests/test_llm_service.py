import pytest
import asyncio
from app.core.llm_service import (
    BaseLLMService,
    NeuraXBase,
    NeuraXCode,
    NeuraXCreative,
    NeuraXAnalysis,
    ExampleLLMService,
    LLMMessage,
    LLMMessageType,
    get_llm_service
)

@pytest.mark.asyncio
async def test_neurax_base():
    """Test NeuraX Base model"""
    llm = NeuraXBase(model_name="NeuraX-Base-Test")

    messages = [
        LLMMessage(
            content="Hello, how are you?",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]

    response = await llm.generate_response(messages)

    assert response.model_name == "NeuraX-Base-Test"
    assert response.message_type == LLMMessageType.TEXT
    assert "NeuraX Base model" in response.content
    assert len(response.content) > 0

@pytest.mark.asyncio
async def test_neurax_code():
    """Test NeuraX Code model"""
    llm = NeuraXCode(model_name="NeuraX-Code-Test")

    messages = [
        LLMMessage(
            content="Write a Python function to calculate factorial",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]

    response = await llm.generate_response(messages)

    assert response.model_name == "NeuraX-Code-Test"
    assert response.message_type == LLMMessageType.CODE
    assert "def solve_problem()" in response.content
    assert "factorial" in response.content.lower()

@pytest.mark.asyncio
async def test_neurax_creative():
    """Test NeuraX Creative model"""
    llm = NeuraXCreative(model_name="NeuraX-Creative-Test")

    messages = [
        LLMMessage(
            content="Tell me a story about a robot",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]

    response = await llm.generate_response(messages)

    assert response.model_name == "NeuraX-Creative-Test"
    assert response.message_type == LLMMessageType.TEXT
    assert "story" in response.content.lower()
    assert "robot" in response.content.lower()

@pytest.mark.asyncio
async def test_neurax_analysis():
    """Test NeuraX Analysis model"""
    llm = NeuraXAnalysis(model_name="NeuraX-Analysis-Test")

    messages = [
        LLMMessage(
            content="Analyze the sales data for Q1",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]

    response = await llm.generate_response(messages)

    assert response.model_name == "NeuraX-Analysis-Test"
    assert response.message_type == LLMMessageType.TEXT
    assert "Analysis" in response.content
    assert "Executive Summary" in response.content

@pytest.mark.asyncio
async def test_get_llm_service_factory():
    """Test the factory function"""
    # Test NeuraX variants
    base_llm = get_llm_service("base")
    assert isinstance(base_llm, NeuraXBase)
    assert base_llm.model_name == "NeuraX-Base"

    code_llm = get_llm_service("code")
    assert isinstance(code_llm, NeuraXCode)
    assert code_llm.model_name == "NeuraX-Code"

    creative_llm = get_llm_service("creative")
    assert isinstance(creative_llm, NeuraXCreative)
    assert creative_llm.model_name == "NeuraX-Creative"

    analysis_llm = get_llm_service("analysis")
    assert isinstance(analysis_llm, NeuraXAnalysis)
    assert analysis_llm.model_name == "NeuraX-Analysis"

    # Test custom fallback
    custom_llm = get_llm_service("custom")
    assert isinstance(custom_llm, ExampleLLMService)
    assert custom_llm.model_name == "custom-llm"

    # Test default
    default_llm = get_llm_service()
    assert isinstance(default_llm, NeuraXBase)
    assert default_llm.model_name == "NeuraX-Base"

@pytest.mark.asyncio
async def test_message_preparation():
    """Test message preparation for LLM"""
    llm = NeuraXBase()

    chat_messages = [
        {
            "content": "Hello",
            "message_type": "text",
            "is_ai": False,
            "user_id": 1,
            "created_at": "2023-01-01T00:00:00"
        },
        {
            "content": "Hi there!",
            "message_type": "text",
            "is_ai": True,
            "user_id": 0,
            "created_at": "2023-01-01T00:00:01"
        }
    ]

    llm_messages = llm.prepare_messages_for_llm(chat_messages)

    assert len(llm_messages) == 2
    assert llm_messages[0].content == "Hello"
    assert llm_messages[0].is_ai == False
    assert llm_messages[0].user_id == 1
    assert llm_messages[0].message_type == LLMMessageType.TEXT

    assert llm_messages[1].content == "Hi there!"
    assert llm_messages[1].is_ai == True
    assert llm_messages[1].user_id == 0
    assert llm_messages[1].message_type == LLMMessageType.TEXT

if __name__ == "__main__":
    pytest.main([__file__, "-v"])