"""
LLM Service for NovaMind AI
This service provides an interface for integrating custom LLM models.
Users can implement their own LLM by extending the BaseLLMService class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
from enum import Enum


class LLMMessageType(Enum):
    """Types of messages that can be processed by the LLM"""
    TEXT = "text"
    CODE = "code"
    IMAGE = "image"
    FILE = "file"


@dataclass
class LLMMessage:
    """Represents a message in the conversation"""
    content: str
    message_type: LLMMessageType
    is_ai: bool
    user_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """Represents a response from the LLM"""
    content: str
    message_type: LLMMessageType
    metadata: Dict[str, Any]
    model_name: str
    tokens_used: Optional[int] = None


class BaseLLMService(ABC):
    """
    Abstract base class for LLM services.
    Users should extend this class to implement their own LLM integration.
    """

    def __init__(self, model_name: str = "custom-llm"):
        self.model_name = model_name

    @abstractmethod
    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM based on conversation history.

        Args:
            messages: List of conversation messages (chronological order)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters

        Returns:
            LLMResponse: The generated response
        """
        pass

    @abstractmethod
    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the LLM.

        Args:
            messages: List of conversation messages (chronological order)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters

        Yields:
            str: Chunks of the generated response
        """
        pass

    def prepare_messages_for_llm(
        self,
        chat_messages: List[Dict[str, Any]]
    ) -> List[LLMMessage]:
        """
        Convert internal chat message format to LLMMessage format.
        Override this if your LLM requires special formatting.

        Args:
            chat_messages: List of message dictionaries from Redis/storage

        Returns:
            List[LLMMessage]: Formatted messages for LLM consumption
        """
        llm_messages = []
        for msg in chat_messages:
            # Convert string message_type to enum
            msg_type_str = msg.get("message_type", "text")
            try:
                msg_type = LLMMessageType(msg_type_str)
            except ValueError:
                msg_type = LLMMessageType.TEXT  # Default fallback

            llm_messages.append(LLMMessage(
                content=msg.get("content", ""),
                message_type=msg_type,
                is_ai=bool(msg.get("is_ai", False)),
                user_id=msg.get("user_id"),
                metadata=msg.get("metadata")
            ))

        return llm_messages

    def extract_response_metadata(
        self,
        llm_response: LLMResponse
    ) -> Dict[str, Any]:
        """
        Extract metadata from LLM response for storage in chat metadata.
        Override this if you need to capture additional information.

        Args:
            llm_response: Response from the LLM service

        Returns:
            Dict[str, Any]: Metadata to store with the message
        """
        metadata = {
            "model": llm_response.model_name,
        }

        if llm_response.tokens_used is not None:
            metadata["tokens_used"] = llm_response.tokens_used

        # Include any additional metadata from the response
        if llm_response.metadata:
            metadata.update(llm_response.metadata)

        return metadata


# NeuraX Model Family - Different variants for different tasks
class NeuraXBase(BaseLLMService):
    """
    NeuraX Base - General purpose model for everyday conversations
    Good for: General Q&A, casual conversation, basic reasoning
    """

    def __init__(self, model_name: str = "NeuraX-Base"):
        super().__init__(model_name)
        # In production: Initialize your base NeuraX model here
        # Example: self.model = load_neurax_base_model()

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a general purpose response.
        """
        # Extract user message
        user_message = ""
        for msg in reversed(messages):
            if not msg.is_ai and msg.content.strip():
                user_message = msg.content
                break

        if not user_message:
            user_message = "Hello"

        # General purpose response
        response_content = f"""Thank you for your message: "{user_message}"

This is a response from your NeuraX Base model - designed for general purpose conversations and everyday tasks.

[In production, this would use your actual NeuraX-Base model to generate a thoughtful, contextual response based on the conversation history.]

[Model: {self.model_name}]"""

        return LLMResponse(
            content=response_content,
            message_type=LLMMessageType.TEXT,
            metadata={
                "model_variant": "NeuraX-Base",
                "use_case": "general_conversation",
                "processed_by": "neurax_base_service"
            },
            model_name=self.model_name,
            tokens_used=len(response_content.split())
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming general purpose response.
        """
        response = await self.generate_response(messages, temperature, max_tokens, **kwargs)
        words = response.content.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield " " + word
            import asyncio
            await asyncio.sleep(0.03)  # Faster streaming for base model


class NeuraXCode(BaseLLMService):
    """
    NeuraX Code - Specialized model for code generation and technical tasks
    Good for: Programming, debugging, technical documentation, algorithms
    """

    def __init__(self, model_name: str = "NeuraX-Code"):
        super().__init__(model_name)
        # In production: Initialize your code-specialized NeuraX model here
        # Example: self.model = load_neurax_code_model()

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.2,  # Lower temperature for more focused code
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a code-focused response.
        """
        # Extract user message
        user_message = ""
        for msg in reversed(messages):
            if not msg.is_ai and msg.content.strip():
                user_message = msg.content
                break

        if not user_message:
            user_message = "Write a simple Python function"

        # Determine if this is a code request
        is_code_request = any(keyword in user_message.lower() for keyword in [
            "code", "program", "function", "class", "algorithm", "debug",
            "python", "javascript", "java", "cpp", "sql", "html", "css",
            "script", "software", "develop", "implement"
        ])

        if is_code_request:
            response_content = f"""Here's a code solution for your request:

```python
# Solution for: {user_message}
# [This is where your actual NeuraX-Code model would generate code]

def solve_problem():
    '''
    Solve the problem: {user_message}
    This function was generated by your NeuraX-Code model.
    '''
    # TODO: Implement the actual solution based on '{user_message}'
    # Your NeuraX-Code model would generate the appropriate implementation here

    result = "Implementation would go here"
    return result

# Example usage:
if __name__ == "__main__":
    solution = solve_problem()
    print(solution)
```

[Response generated by your NeuraX-Code model: {self.model_name}]"""
            response_type = LLMMessageType.CODE
        else:
            # Fallback to general response if not clearly a code request
            response_content = f"""I understand you're asking about: "{user_message}"

While I can help with general questions, I'm specialized in code generation and technical tasks. For best results with coding tasks, please include keywords like "code", "program", "function", or specify a programming language.

[Response generated by your NeuraX-Code model: {self.model_name}]"""
            response_type = LLMMessageType.TEXT

        return LLMResponse(
            content=response_content,
            message_type=response_type,
            metadata={
                "model_variant": "NeuraX-Code",
                "use_case": "code_generation",
                "temperature": temperature,
                "is_code_request": is_code_request,
                "processed_by": "neurax_code_service"
            },
            model_name=self.model_name,
            tokens_used=len(response_content.split())
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming code-focused response.
        """
        response = await self.generate_response(messages, temperature, max_tokens, **kwargs)
        words = response.content.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield " " + word
            import asyncio
            await asyncio.sleep(0.04)  # Slightly slower for code precision


class NeuraXCreative(BaseLLMService):
    """
    NeuraX Creative - Specialized model for creative writing and ideation
    Good for: Story writing, brainstorming, creative content, design ideas
    """

    def __init__(self, model_name: str = "NeuraX-Creative"):
        super().__init__(model_name)
        # In production: Initialize your creative-specialized NeuraX model here
        # Example: self.model = load_neurax_creative_model()

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.9,  # Higher temperature for more creativity
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a creative response.
        """
        # Extract user message
        user_message = ""
        for msg in reversed(messages):
            if not msg.is_ai and msg.content.strip():
                user_message = msg.content
                break

        if not user_message:
            user_message = "Tell me a story"

        # Determine if this is a creative request
        is_creative_request = any(keyword in user_message.lower() for keyword in [
            "story", "creative", "imagine", "design", "brainstorm", "idea",
            "novel", "poem", "song", "character", "plot", "setting",
            "creative writing", "fiction", "art", "design", "concept"
        ])

        if is_creative_request:
            response_content = f"""Here's a creative response to your request: "{user_message}"

[This is where your actual NeuraX-Creative model would generate creative content]

Once upon a time, in a digital realm not so far away, there lived an AI named NeuraX who loved to create. When asked to "{user_message}", NeuraX's creative circuits sparked with inspiration...

The story unfolded with vivid characters, imaginative settings, and unexpected twists that showcased the unique creative capabilities of the NeuraX-Creative model.

And they all lived happily ever after, creating amazing content together.

[Response generated by your NeuraX-Creative model: {self.model_name}]"""
            response_type = LLMMessageType.TEXT
        else:
            response_content = f"""Thank you for sharing: "{user_message}"

While I can engage in general conversation, I'm specifically designed for creative tasks like storytelling, brainstorming, and ideation. For the most creative results, try asking me to:
- "Tell a story about..."
- "Brainstorm ideas for..."
- "Design a character who..."
- "Write a poem about..."

[Response generated by your NeuraX-Creative model: {self.model_name}]"""
            response_type = LLMMessageType.TEXT

        return LLMResponse(
            content=response_content,
            message_type=response_type,
            metadata={
                "model_variant": "NeuraX-Creative",
                "use_case": "creative_writing",
                "temperature": temperature,
                "is_creative_request": is_creative_request,
                "processed_by": "neurax_creative_service"
            },
            model_name=self.model_name,
            tokens_used=len(response_content.split())
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.9,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming creative response.
        """
        response = await self.generate_response(messages, temperature, max_tokens, **kwargs)
        words = response.content.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield " " + word
            import asyncio
            await asyncio.sleep(0.02)  # Faster streaming for creative flow


class NeuraXAnalysis(BaseLLMService):
    """
    NeuraX Analysis - Specialized model for analytical and reasoning tasks
    Good for: Data analysis, logical reasoning, problem solving, research
    """

    def __init__(self, model_name: str = "NeuraX-Analysis"):
        super().__init__(model_name)
        # In production: Initialize your analysis-specialized NeuraX model here
        # Example: self.model = load_neurax_analysis_model()

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.4,  # Lower temperature for more analytical precision
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate an analytical response.
        """
        # Extract user message
        user_message = ""
        for msg in reversed(messages):
            if not msg.is_ai and msg.content.strip():
                user_message = msg.content
                break

        if not user_message:
            user_message = "Analyze this situation"

        # Determine if this is an analytical request
        is_analysis_request = any(keyword in user_message.lower() for keyword in [
            "analyze", "analysis", "data", "statistics", "research", "compare",
            "evaluate", "assess", "calculate", "reason", "logic", "problem",
            "solution", "investigate", "examine", "study", "report"
        ])

        if is_analysis_request:
            response_content = f"""Analysis of: "{user_message}"

[This is where your actual NeuraX-Analysis model would perform deep analytical reasoning]

**Executive Summary:**
Based on the input "{user_message}", here is a structured analysis:

**Key Findings:**
1. The request involves analytical thinking about: {user_message[:50]}{'...' if len(user_message) > 50 else ''}
2. Multiple approaches could be considered for addressing this query
3. Contextual factors from the conversation history should be weighed

**Detailed Analysis:**
- **Approach 1**: [Your NeuraX-Analysis model would detail this]
- **Approach 2**: [Your NeuraX-Analysis model would detail this]
- **Recommendation**: Based on the analysis, the recommended approach would be...

**Next Steps:**
1. Gather additional data if needed
2. Apply the recommended methodology
3. Validate results through testing or peer review

[Response generated by your NeuraX-Analysis model: {self.model_name}]"""
            response_type = LLMMessageType.TEXT
        else:
            response_content = f"""Thank you for your query: "{user_message}"

While I can handle general questions, I'm specifically optimized for analytical tasks like data analysis, logical reasoning, and problem-solving. For best analytical results, consider framing your request with terms like:
- "Analyze the data showing..."
- "Compare the pros and cons of..."
- "Evaluate the effectiveness of..."
- "What are the implications of..."
- "How would you solve..."
- "Research the topic of..."

[Response generated by your NeuraX-Analysis model: {self.model_name}]"""
            response_type = LLMMessageType.TEXT

        return LLMResponse(
            content=response_content,
            message_type=response_type,
            metadata={
                "model_variant": "NeuraX-Analysis",
                "use_case": "analytical_reasoning",
                "temperature": temperature,
                "is_analysis_request": is_analysis_request,
                "processed_by": "neurax_analysis_service"
            },
            model_name=self.model_name,
            tokens_used=len(response_content.split())
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.4,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming analytical response.
        """
        response = await self.generate_response(messages, temperature, max_tokens, **kwargs)
        words = response.content.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield " " + word
            import asyncio
            await asyncio.sleep(0.05)  # Moderate streaming for analysis


# Example implementation for users to reference/customize
class ExampleLLMService(BaseLLMService):
    """
    Example LLM implementation showing how to integrate a custom model.
    Users should replace this with their own implementation.
    """

    def __init__(self, model_name: str = "example-llm"):
        super().__init__(model_name)
        # Initialize your LLM here (e.g., load model, set up inference pipeline)
        # Example:
        # self.model = self.load_your_model()
        # self.tokenizer = self.load_your_tokenizer()

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Example implementation - replace with your actual LLM inference.
        """
        # TODO: Replace this with your actual LLM inference code
        # Example structure:
        #
        # 1. Preprocess messages for your model format
        # formatted_prompt = self.format_prompt_for_model(messages)
        #
        # 2. Run inference
        # raw_output = self.model.generate(
        #     formatted_prompt,
        #     temperature=temperature,
        #     max_length=max_tokens,
        #     **kwargs
        # )
        #
        # 3. Postprocess output
        # response_text = self.postprocess_output(raw_output)
        #
        # 4. Determine message type if needed
        # response_type = self.detect_response_type(response_text)
        #
        # 5. Calculate tokens used (if available)
        # tokens_used = self.calculate_tokens_used(raw_output)

        # Placeholder response - REPLACE THIS WITH YOUR ACTUAL LLM
        user_message = ""
        for msg in reversed(messages):
            if not msg.is_ai and msg.content.strip():
                user_message = msg.content
                break

        if not user_message:
            user_message = "Hello"

        # Simulate different response types based on user input
        if "code" in user_message.lower() or "program" in user_message.lower():
            response_content = f"""Here's a code solution for your request:

```python
# Solution for: {user_message}
# [This is where your actual LLM would generate code]

def example_solution():
    '''Example function - replace with your LLM's output'''
    # TODO: Implement based on '{user_message}'
    result = "This is a placeholder response from your custom LLM"
    return result

# Example usage:
if __name__ == "__main__":
    print(example_solution())
```

[Response generated by your custom LLM: {self.model_name}]"""
            response_type = LLMMessageType.CODE
        elif "image" in user_message.lower() or "picture" in user_message.lower() or "draw" in user_message.lower():
            response_content = f"""I've processed your image request: "{user_message}"

[In a production implementation, your LLM would either:
1. Generate an image directly (if multimodal)
2. Provide a detailed description for image generation
3. Return parameters for an image generation model]

[Response generated by your custom LLM: {self.model_name}]"""
            response_type = LLMMessageType.IMAGE
        else:
            response_content = f"""Thank you for your message: "{user_message}"

This is a placeholder response showing where your custom LLM's output would appear.
To use your actual LLM model:
1. Replace the ExampleLLMService class with your implementation
2. Or modify the BaseLLMService methods to call your model directly
3. Ensure your model is properly loaded and accessible

[Response generated by your custom LLM: {self.model_name}]"""
            response_type = LLMMessageType.TEXT

        return LLMResponse(
            content=response_content,
            message_type=response_type,
            metadata={
                "processed_by": "example_llm_service",
                "input_length": len(user_message) if user_message else 0
            },
            model_name=self.model_name,
            tokens_used=len(response_content.split())  # Rough estimate
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Example streaming implementation - replace with your actual streaming LLM.
        """
        # Get the full response first (in a real implementation, this would be truly streaming)
        response = await self.generate_response(messages, temperature, max_tokens, **kwargs)

        # Simulate streaming by yielding chunks
        words = response.content.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield " " + word
            # Simulate network/processing delay
            import asyncio
            await asyncio.sleep(0.05)  # 50ms per word


# Factory function to get LLM service instance
def get_llm_service(model_variant: str = "local") -> BaseLLMService:
    """
    Factory function to get the LLM service instance.
    Users can specify which NeuraX variant to use, or provide their own implementation.

    Args:
        model_variant: Which variant to use. Default is ``"local"`` — the
                       in-process rule engine, always available. If Ollama
                       is running and ``OLLAMA_DEFAULT_MODEL`` is set (or
                       ``"local"`` is passed and Ollama is reachable), we
                       route through Ollama instead. Other supported values:
                       "base", "code", "creative", "analysis" (legacy
                       NeuraX template variants) and "custom" (placeholder
                       for users to swap in a foundation-model backend).

    Returns:
        BaseLLMService: An instance of the LLM service to use
    """
    # Imported here to avoid a circular import: local_engine / ollama_service
    # both import from this module.
    from .local_engine import NovaMindLocal
    from .ollama_service import OllamaChatService, ollama_reachable, select_default_ollama_model
    import os

    # When the caller doesn't pin a specific variant, prefer Ollama if it's
    # reachable so the in-app chat ("AI working properly") actually uses a
    # real model. Users on Ollama=off keep the rule engine.
    if model_variant.lower() in ("local", "auto") and ollama_reachable():
        default_model = os.environ.get("OLLAMA_DEFAULT_MODEL") or select_default_ollama_model()
        return OllamaChatService(model_name=default_model)

    variant_map = {
        "local": NovaMindLocal,
        "base": NeuraXBase,
        "code": NeuraXCode,
        "creative": NeuraXCreative,
        "analysis": NeuraXAnalysis,
        "custom": ExampleLLMService,
    }

    service_class = variant_map.get(model_variant.lower(), NovaMindLocal)

    if model_variant.lower() == "custom":
        return service_class(model_name="custom-llm")
    elif model_variant.lower() == "local":
        return service_class(model_name="NovaMind-local-v1")
    else:
        return service_class()