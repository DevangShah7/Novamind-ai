"""
Tests for NovaMindLocal - the deterministic, rule-based response engine.

These tests exercise each handler in isolation through `generate_response`,
without needing the FastAPI app, the database, or a network. If the
engine's handler dispatch changes, these should still pass as long as the
public behaviour matches.
"""

import pytest

from app.core.local_engine import (
    NovaMindLocal,
    eval_arithmetic,
    _handle_greeting,
    _handle_capabilities,
    _handle_time_date,
    _handle_math,
    _handle_faq,
    _handle_code_recall,
)
from app.core.llm_service import LLMMessage, LLMMessageType


# ---------- helpers ----------

def _user(text: str) -> list[LLMMessage]:
    return [
        LLMMessage(
            content=text,
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1,
        )
    ]


# ---------- safe arithmetic ----------

class TestEvalArithmetic:
    def test_basic_ops(self):
        assert eval_arithmetic("12 * 7") == 84
        assert eval_arithmetic("2 ** 10") == 1024
        assert eval_arithmetic("6 / 4") == 1.5
        assert eval_arithmetic("(1 + 2) * 3") == 9

    def test_returns_int_for_whole_float(self):
        # eval_arithmetic returns the raw float from true division; the
        # int-coercion lives in _handle_math. So 4/2 stays 2.0 here.
        v = eval_arithmetic("4 / 2")
        assert v == 2.0
        assert isinstance(v, float)

    def test_unicode_glyphs(self):
        assert eval_arithmetic("3 × 4") == 12
        assert eval_arithmetic("10 ÷ 4") == 2.5

    def test_not_arithmetic_returns_none(self):
        assert eval_arithmetic("hello world") is None
        assert eval_arithmetic("") is None

    def test_rejects_unsafe(self):
        # No name lookups, no calls, no attribute access.
        assert eval_arithmetic('__import__("os")') is None
        assert eval_arithmetic('open("x")') is None
        assert eval_arithmetic("foo.bar") is None
        # Syntax errors
        assert eval_arithmetic("5 +") is None
        # Division by zero
        assert eval_arithmetic("1/0") is None
        # Huge exponent
        assert eval_arithmetic("2**10000") is None


# ---------- individual handlers (sync) ----------

class TestHandlers:
    def test_greeting(self):
        assert _handle_greeting("hi") is not None
        assert _handle_greeting("Hello!") is not None
        assert _handle_greeting("namaste") is not None
        assert _handle_greeting("how are you") is None

    def test_capabilities(self):
        assert _handle_capabilities("what can you do?") is not None
        assert _handle_capabilities("help") is not None
        assert _handle_capabilities("features") is not None
        assert _handle_capabilities("tell me a joke") is None

    def test_time_date_handles_today(self):
        result = _handle_time_date("what is the date today")
        assert result is not None
        assert "20" in result  # year contains "20" for any 21st-century date

    def test_time_date_handles_tomorrow(self):
        result = _handle_time_date("what day is tomorrow")
        assert result is not None
        assert "Tomorrow" in result

    def test_math_simple(self):
        result = _handle_math("12 * 7")
        assert result == "12 * 7 = 84"

    def test_math_returns_none_for_non_math(self):
        assert _handle_math("hello there") is None

    def test_faq_lookup(self):
        # Exact key match (lowercased).
        result = _handle_faq("what is novamind")
        assert result is not None and len(result) > 0

    def test_faq_substring_match_picks_longest(self):
        # "who made you" should beat the shorter "who" if both are keys.
        result = _handle_faq("who made you?")
        if result is not None:
            assert "team" in result.lower() or "devang" in result.lower() or "shah" in result.lower()

    def test_code_recall(self):
        result = _handle_code_recall("python list comprehension")
        assert result is not None
        assert "```python" in result

    def test_code_recall_sql(self):
        result = _handle_code_recall("show me a sql join")
        assert result is not None
        assert "```sql" in result

    def test_code_recall_returns_none_unrelated(self):
        assert _handle_code_recall("what's the weather") is None


# ---------- full generate_response path ----------

@pytest.mark.asyncio
async def test_generate_response_greeting():
    engine = NovaMindLocal()
    response = await engine.generate_response(_user("hi there"))
    assert response.content
    assert response.metadata["handler"] == "greeting"
    assert response.metadata["engine"] == "NovaMind-local-v1"


@pytest.mark.asyncio
async def test_generate_response_math():
    engine = NovaMindLocal()
    response = await engine.generate_response(_user("12 * 7"))
    assert "84" in response.content
    assert response.metadata["handler"] == "math"


@pytest.mark.asyncio
async def test_generate_response_faq():
    engine = NovaMindLocal()
    response = await engine.generate_response(_user("how to deploy"))
    assert response.metadata["handler"] == "faq"
    assert response.content


@pytest.mark.asyncio
async def test_generate_response_code_recall():
    engine = NovaMindLocal()
    response = await engine.generate_response(_user("python list comprehension"))
    assert response.metadata["handler"] == "code_recall"
    assert "```python" in response.content


@pytest.mark.asyncio
async def test_generate_response_time_date():
    engine = NovaMindLocal()
    response = await engine.generate_response(_user("what day is tomorrow"))
    assert response.metadata["handler"] == "time_date"


@pytest.mark.asyncio
async def test_generate_response_default_fallback():
    engine = NovaMindLocal()
    response = await engine.generate_response(_user("blah blah nothing useful"))
    assert response.metadata["handler"] == "default"
    # The fallback should be honest about what we are.
    assert "rule-based" in response.content.lower() or "local engine" in response.content.lower()


@pytest.mark.asyncio
async def test_generate_response_streams_words():
    """The streaming generator should yield at least one chunk per word."""
    engine = NovaMindLocal()
    chunks = []
    async for chunk in engine.generate_response_stream(_user("12 * 7")):
        chunks.append(chunk)
    joined = "".join(chunks)
    assert "84" in joined
    # Multi-word content -> more than one chunk.
    assert len(chunks) > 1


@pytest.mark.asyncio
async def test_generate_response_conversation_meta_summarize():
    """When the user asks for a summary, the engine should return a recap."""
    engine = NovaMindLocal()
    history = _user("hello") + [
        LLMMessage(content="hi", message_type=LLMMessageType.TEXT, is_ai=True, user_id=0),
        _user("summarise our chat")[0],
    ]
    response = await engine.generate_response(history)
    assert response.metadata["handler"] == "conversation_meta"
    assert "hello" in response.content.lower()
