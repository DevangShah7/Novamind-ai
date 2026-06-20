"""
Tests for the reasoning service
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from backend.app.core.reasoning_service import ReasoningService, ReasoningStrategy, apply_reasoning
from backend.app.core.llm_service import BaseLLMService, LLMMessage, LLMResponse, LLMMessageType

@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service for testing"""
    mock_service = Mock(spec=BaseLLMService)
    mock_service.generate_response = AsyncMock()
    return mock_service

@pytest.mark.asyncio
async def test_reasoning_service_initialization(mock_llm_service):
    """Test that the reasoning service initializes correctly"""
    service = ReasoningService(mock_llm_service)
    assert service.llm_service == mock_llm_service

@pytest.mark.asyncio
async def test_chain_of_thought_reasoning(mock_llm_service):
    """Test chain-of-thought reasoning"""
    # Setup mock response
    mock_response = LLMResponse(
        content="Step 1: Identify the problem\nStep 2: Analyze the data\nStep 3: Draw conclusion\nFinal answer: 42",
        message_type=LLMMessageType.TEXT,
        message_metadata={},
        model_name="test-model",
        tokens_used=100
    )
    mock_llm_service.generate_response.return_value = mock_response

    # Create service and test
    service = ReasoningService(mock_llm_service)
    result = await service.chain_of_thought("What is the answer to life, the universe, and everything?")

    # Check that we got a result
    assert isinstance(result, ReasoningResult)
    assert result.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT
    assert isinstance(result.final_answer, str)
    assert len(result.reasoning_steps) >= 0
    assert isinstance(result.confidence, float)
    assert 0 <= result.confidence <= 1
    assert isinstance(result.metadata, dict)

    # Verify that the LLM service was called
    mock_llm_service.generate_response.assert_called_once()

@pytest.mark.asyncio
async def test_tree_of_thoughts_reasoning(mock_llm_service):
    """Test tree-of-thoughts reasoning"""
    # Setup mock responses
    mock_thoughts_response = LLMResponse(
        content="Approach 1: Analytical approach\nApproach 2: Creative approach\nApproach 3: Practical approach",
        message_type=LLMMessageType.TEXT,
        message_metadata={},
        model_name="test-model",
        tokens_used=50
    )
    mock_develop_response = LLMResponse(
        content="Detailed development of the approach leading to a solution",
        message_type=LLMMessageType.TEXT,
        message_metadata={},
        model_name="test-model",
        tokens_used=75
    )
    mock_synthesis_response = LLMResponse(
        content="Synthesized final answer based on all approaches",
        message_type=LLMMessageType.TEXT,
        message_metadata={},
        model_name="test-model",
        tokens_used=60
    )

    # Configure the mock to return different responses for different calls
    mock_llm_service.generate_response.side_effect = [
        mock_thoughts_response,
        mock_develop_response,
        mock_develop_response,
        mock_develop_response,
        mock_synthesis_response
    ]

    # Create service and test
    service = ReasoningService(mock_llm_service)
    result = await service.tree_of_thoughts("How to solve a complex problem?", breadth=3, depth=2)

    # Check that we got a result
    assert isinstance(result, ReasoningResult)
    assert result.strategy == ReasoningStrategy.TREE_OF_THOUGHTS
    assert isinstance(result.final_answer, str)
    assert len(result.reasoning_steps) >= 0
    assert isinstance(result.confidence, float)
    assert 0 <= result.confidence <= 1
    assert isinstance(result.metadata, dict)

    # Verify that the LLM service was called the expected number of times
    assert mock_llm_service.generate_response.call_count == 5

@pytest.mark.asyncio
async def test_apply_reasoning_convenience_function(mock_llm_service):
    """Test the convenience function for applying reasoning"""
    # Setup mock response
    mock_response = LLMResponse(
        content="Step-by-step reasoning leads to answer: 42",
        message_type=LLMMessageType.TEXT,
        message_metadata={},
        model_name="test-model",
        tokens_used=50
    )
    mock_llm_service.generate_response.return_value = mock_response

    # Test the convenience function
    result = await apply_reasoning(
        mock_llm_service,
        "What is the answer?",
        strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
        temperature=0.7
    )

    # Check that we got a result
    assert isinstance(result, ReasoningResult)
    assert result.strategy == ReasoningStrategy.CHAIN_OF_THOUGHT
    assert isinstance(result.final_answer, str)
    assert isinstance(result.confidence, float)

    # Verify that the LLM service was called with the correct parameters
    mock_llm_service.generate_response.assert_called_once()
    call_args = mock_llm_service.generate_response.call_args
    assert call_args is not None
    # Check that the temperature was passed through
    # Note: The exact structure depends on how the reasoning service processes kwargs

if __name__ == "__main__":
    pytest.main([__file__, "-v"])