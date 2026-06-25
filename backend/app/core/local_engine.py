"""
NovaMindLocal — a deterministic, rule-based response engine.

This is NOT a foundation model. It exists to give the NovaMind AI app a
real backend (no third-party API, no per-token cost) that handles a
useful subset of conversational patterns:

  - Greetings, time-of-day variants
  - Time / date questions ("what day is tomorrow", "next monday")
  - Arithmetic (safe AST evaluation, no eval)
  - FAQ lookups (loaded from backend/data/novamind_faq.json)
  - Code snippet recall (loaded from backend/data/code_snippets.json)
  - Conversation meta ("summarise our chat", "what did I say earlier")
  - Honest fallback that lists capabilities

It implements the same `BaseLLMService` interface the rest of the backend
uses, so swapping engines is a one-line change in `get_llm_service()`.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import operator
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from .llm_service import (
    BaseLLMService,
    LLMMessage,
    LLMMessageType,
    LLMResponse,
)

logger = logging.getLogger(__name__)

# ---------- safe AST arithmetic ----------

_BIN_OPS: Dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: Dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class _MathError(Exception):
    """Raised when an arithmetic expression can't be safely evaluated."""


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise _MathError("exponent too large")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise _MathError(f"unsupported expression: {type(node).__name__}")


def eval_arithmetic(text: str) -> Optional[float]:
    """Try to evaluate `text` as arithmetic. Returns None if it isn't."""
    # Normalise common glyphs to ASCII so users can type × ÷ − etc.
    normalised = (
        text.replace("×", "*").replace("x", "*").replace("÷", "/")
        .replace("−", "-").replace("^", "**").replace(",", "")
    )
    # Strip trailing punctuation/whitespace.
    candidate = normalised.strip().strip(".?=")
    # Must contain at least one operator or be a numeric expression.
    if not re.search(r"[\d]", candidate):
        return None
    try:
        tree = ast.parse(candidate, mode="eval")
    except SyntaxError:
        return None
    try:
        return _safe_eval(tree)
    except (ZeroDivisionError, _MathError):
        return None


# ---------- data loaders ----------

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_FAQ_PATH = _DATA_DIR / "novamind_faq.json"
_SNIPPETS_PATH = _DATA_DIR / "code_snippets.json"

_FAQ_CACHE: Optional[Dict[str, str]] = None
_SNIPPETS_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def _load_faq() -> Dict[str, str]:
    global _FAQ_CACHE
    if _FAQ_CACHE is not None:
        return _FAQ_CACHE
    try:
        with _FAQ_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("FAQ file not found at %s", _FAQ_PATH)
        data = {}
    _FAQ_CACHE = {k.lower(): v for k, v in data.items()}
    return _FAQ_CACHE


def _load_snippets() -> Dict[str, Dict[str, str]]:
    global _SNIPPETS_CACHE
    if _SNIPPETS_CACHE is not None:
        return _SNIPPETS_CACHE
    try:
        with _SNIPPETS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("Code snippet file not found at %s", _SNIPPETS_PATH)
        data = {}
    _SNIPPETS_CACHE = {lang.lower(): {k.lower(): v for k, v in snippets.items()} for lang, snippets in data.items()}
    return _SNIPPETS_CACHE


# ---------- handlers ----------

_GREETING_WORDS = {
    "hi", "hello", "hey", "hiya", "howdy", "namaste", "hola", "yo", "sup",
    "good morning", "good afternoon", "good evening", "morning", "evening",
}

_GREETING_RESPONSES = [
    "Hi! I'm NovaMind local engine. Ask me a question, do some math, or try /help in the CLI.",
    "Hello! I can do math, recall code snippets, answer FAQs, and reason about time/date. What do you need?",
    "Hey there. I'm a small rule-based engine — no foundation model, no external API. Try 'what can you do?'",
]


def _handle_greeting(text: str) -> Optional[str]:
    stripped = text.strip().lower().strip(".!?")
    if stripped in _GREETING_WORDS or any(stripped.startswith(w + " ") for w in _GREETING_WORDS):
        return random.choice(_GREETING_RESPONSES)
    return None


def _handle_capabilities(text: str) -> Optional[str]:
    if re.search(r"what can you do|help|features|capabilities", text.lower()):
        return (
            "I can:\n"
            "  • answer FAQs about NovaMind (try 'what is novamind' or 'how to deploy')\n"
            "  • do arithmetic (try '12 * 7' or '2 ** 10')\n"
            "  • tell you the time and date (try 'what day is tomorrow')\n"
            "  • recall pre-loaded code snippets (try 'python list comprehension' or 'sql join')\n"
            "  • summarise our conversation (try 'summarise our chat')\n\n"
            "I'm a rule-based local engine — not a foundation model — so I won't match GPT/Claude "
            "on open-ended chat, but I'm free, fast, and private. The codebase (backend/app/core/"
            "local_engine.py) is plain Python and easy to extend."
        )
    return None


_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _next_weekday(now: datetime, target: int) -> datetime:
    days_ahead = (target - now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return now + timedelta(days=days_ahead)


def _handle_time_date(text: str) -> Optional[str]:
    low = text.lower().strip()
    now = datetime.now()
    if re.search(r"\bwhat(?:'s| is)?\s+(?:the\s+)?(?:today'?s?\s+)?date\b|\bdate today\b", low):
        return f"Today is {now.strftime('%A, %d %B %Y')}."
    if re.search(r"\bwhat(?:'s| is)?\s+the\s+time\b|\bcurrent time\b|\btime now\b", low):
        return f"It's {now.strftime('%H:%M')} on {now.strftime('%A')}."
    if "tomorrow" in low:
        return f"Tomorrow is {(now + timedelta(days=1)).strftime('%A, %d %B %Y')}."
    if "yesterday" in low:
        return f"Yesterday was {(now - timedelta(days=1)).strftime('%A, %d %B %Y')}."
    m = re.search(r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", low)
    if m:
        target = _DAY_NAMES.index(m.group(1))
        return f"Next {m.group(1).title()} is {_next_weekday(now, target).strftime('%d %B %Y')}."
    m = re.search(r"\b(?:in|after)\s+(\d+)\s+days?\b", low)
    if m:
        d = int(m.group(1))
        return f"In {d} days it will be {(now + timedelta(days=d)).strftime('%A, %d %B %Y')}."
    return None


def _handle_math(text: str) -> Optional[str]:
    value = eval_arithmetic(text)
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{text.strip().rstrip('?.!')} = {value}"


def _handle_faq(text: str) -> Optional[str]:
    faq = _load_faq()
    low = text.lower().strip().rstrip("?.!")
    if not faq:
        return None
    if low in faq:
        return faq[low]
    # Substring match — pick the longest key that's a substring of the user
    # text, so 'who made you' beats 'who' as a partial hit.
    candidates = [k for k in faq if k in low]
    if not candidates:
        return None
    return faq[max(candidates, key=len)]


_LANG_KEYWORDS = {
    "python": ["python", "py"],
    "javascript": ["javascript", "js", "node", "nodejs"],
    "sql": ["sql", "postgres", "postgresql", "mysql", "sqlite"],
    "bash": ["bash", "shell", "sh", "zsh"],
}

_INTENT_KEYWORDS = [
    "list comprehension", "read file", "write file", "json load", "json dump",
    "http request", "fizzbuzz", "fibonacci", "sort dict", "fetch", "debounce",
    "sort array", "async await", "group by", "join", "pagination", "create table",
    "insert", "update", "delete", "find files", "grep", "curl", "loop", "tar",
    "disk usage",
]


def _handle_code_recall(text: str) -> Optional[str]:
    low = text.lower()
    if not re.search(r"\b(code|snippet|example|how to write|how do i write)\b", low) and \
       not any(intent in low for intent in _INTENT_KEYWORDS):
        return None
    snippets = _load_snippets()
    if not snippets:
        return None
    # Detect language.
    detected_lang = None
    for lang, kws in _LANG_KEYWORDS.items():
        if any(kw in low for kw in kws):
            detected_lang = lang
            break
    # Detect intent.
    detected_intent = None
    for intent in _INTENT_KEYWORDS:
        if intent in low:
            detected_intent = intent
            break
    if detected_lang and detected_intent and detected_intent in snippets.get(detected_lang, {}):
        return f"```{detected_lang}\n{snippets[detected_lang][detected_intent]}\n```"
    if detected_intent:
        for lang, by_intent in snippets.items():
            if detected_intent in by_intent:
                return f"```{lang}\n{by_intent[detected_intent]}\n```"
    if detected_lang and detected_lang in snippets:
        first_intent = next(iter(snippets[detected_lang]))
        return f"```{detected_lang}\n{snippets[detected_lang][first_intent]}\n```"
    return None


def _handle_conversation_meta(text: str, history: List[LLMMessage]) -> Optional[str]:
    low = text.lower()
    user_msgs = [m.content for m in history if not m.is_ai and m.content.strip()]
    if re.search(r"summari[sz]e|summary|recap", low) and len(user_msgs) >= 1:
        if not user_msgs:
            return "We haven't exchanged any messages yet."
        bullets = "\n".join(f"  • {m[:100]}{'…' if len(m) > 100 else ''}" for m in user_msgs[-5:])
        return f"Here's a quick recap of your messages in this chat:\n{bullets}"
    if re.search(r"what did i (?:just\s+)?say|repeat (?:that|my (?:last|previous))", low):
        if not user_msgs:
            return "You haven't said anything yet in this chat."
        return f"You said: \"{user_msgs[-1]}\""
    if re.search(r"how many messages|message count", low):
        return f"We've exchanged {len(user_msgs)} user messages and {sum(1 for m in history if m.is_ai)} assistant messages."
    return None


def _default_fallback(history: List[LLMMessage]) -> str:
    return (
        "I'm NovaMind local engine — a rule-based system, not a foundation model. "
        "I don't have a general conversational model, so I can't answer this from scratch.\n\n"
        "Try one of these:\n"
        "  • a question from the FAQ (e.g. 'how to deploy')\n"
        "  • an arithmetic expression (e.g. '12 * 7')\n"
        "  • 'python list comprehension' or 'sql join' for a code snippet\n"
        "  • 'what can you do' for a full list of capabilities"
    )


# ---------- engine ----------

class NovaMindLocal(BaseLLMService):
    """Rule-based, in-process, no external API."""

    def __init__(self, model_name: str = "NovaMind-local-v1"):
        super().__init__(model_name=model_name)
        # Eager-load data so the first user message doesn't pay a disk-read cost.
        _load_faq()
        _load_snippets()

    @staticmethod
    def _last_user_text(messages: List[LLMMessage]) -> str:
        for m in reversed(messages):
            if not m.is_ai and m.content.strip():
                return m.content
        return ""

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        text = self._last_user_text(messages)
        handler_used: Optional[str] = None
        answer: Optional[str] = None
        for name, fn in (
            ("greeting", _handle_greeting),
            ("capabilities", _handle_capabilities),
            ("math", _handle_math),
            ("time_date", _handle_time_date),
            ("faq", _handle_faq),
            ("code_recall", _handle_code_recall),
            ("conversation_meta", lambda t: _handle_conversation_meta(t, messages)),
        ):
            try:
                result = fn(text)
            except Exception as e:  # pragma: no cover — defensive
                logger.exception("handler %s failed: %s", name, e)
                continue
            if result is not None:
                answer = result
                handler_used = name
                break
        if answer is None:
            answer = _default_fallback(messages)
            handler_used = "default"

        metadata = {
            "engine": self.model_name,
            "engine_type": "rule-based",
            "handler": handler_used,
            "use_case": handler_used or "fallback",
        }
        return LLMResponse(
            content=answer,
            message_type=LLMMessageType.TEXT,
            metadata=metadata,
            model_name=self.model_name,
            tokens_used=len(answer.split()),
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        response = await self.generate_response(messages, temperature, max_tokens, **kwargs)
        words = response.content.split(" ")
        for i, word in enumerate(words):
            yield word if i == 0 else " " + word
            # Tiny per-word delay so the user sees streaming behaviour
            # without making the reply feel sluggish.
            await asyncio.sleep(0.02)
