# NovaMind AI - Custom LLM Integration Guide

This guide explains how to integrate your own LLM model with NovaMind AI to replace the mock responses and example implementations.

## Overview

NovaMind AI has been designed with a pluggable LLM service architecture that allows you to integrate your own custom LLM model without modifying the core application logic. The system uses an abstract base class (`BaseLLMService`) that defines the interface, and you can provide your own implementation.

The system now includes the **NeuraX model family** - 4 specialized variants designed for different tasks:
- **NeuraX-Base**: General purpose conversations
- **NeuraX-Code**: Code generation and technical tasks  
- **NeuraX-Creative**: Creative writing and ideation
- **NeuraX-Analysis**: Analytical reasoning and problem solving

## Files Involved

1. **`/backend/app/core/llm_service.py`** - Contains the LLM service abstraction, NeuraX family, and factory function
2. **`/backend/app/api/endpoints/chats.py** - Uses the LLM service for generating chat responses
3. **(Future)** Other AI endpoints (agents, search, image) can be similarly updated

## Integration Steps

### Step 1: Understand the LLM Service Interface

The core interface is defined in `BaseLLMService`:

```python
class BaseLLMService(ABC):
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
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM"""
        pass
```

### Step 2: Choose Your Integration Approach

You have three options for integrating LLMs with NovaMind AI:

#### Option A: Use NeuraX Model Family (Recommended)
Use one of the pre-built NeuraX variants by specifying the variant when calling `get_llm_service()`:

```python
# In your application code or configuration:
from app.core.llm_service import get_llm_service

# Get NeuraX Base (general purpose)
llm_service = get_llm_service("base")

# Get NeuraX Code (for programming tasks)
llm_service = get_llm_service("code")

# Get NeuraX Creative (for writing tasks)
llm_service = get_llm_service("creative")

# Get NeuraX Analysis (for analytical tasks)
llm_service = get_llm_service("analysis")
```

#### Option B: Create Your Own Custom LLM Implementation
Create a class that extends `BaseLLMService` and implements the abstract methods (see detailed example below).

#### Option C: Configure Default Variant
Modify the default variant used throughout the application by changing the default parameter in `get_llm_service()`.

### Step 2A: Using NeuraX Model Family Details

The NeuraX family includes four specialized models:

#### NeuraX-Base (General Purpose)
- **Best for**: Everyday conversations, general Q&A, casual chat
- **Temperature**: 0.7 (balanced creativity and coherence)
- **Use when**: You need a versatile model for mixed conversation types

#### NeuraX-Code (Programming Specialist)
- **Best for**: Code generation, debugging, technical documentation, algorithms
- **Temperature**: 0.2 (focused, precise outputs)
- **Special features**: Recognizes programming keywords, generates structured code
- **Use when**: Users are asking for code, software development help, or technical solutions

#### NeuraX-Creative (Writing Specialist)
- **Best for**: Story writing, brainstorming, creative content, design ideas
- **Temperature**: 0.9 (high creativity and variety)
- **Special features**: Enhanced imaginative responses, storytelling capabilities
- **Use when**: Users want stories, creative ideas, designs, or artistic content

#### NeuraX-Analysis (Reasoning Specialist)
- **Best for**: Data analysis, logical reasoning, problem solving, research
- **Temperature**: 0.4 (analytical, evidence-based)
- **Special features**: Structured analysis, comparative evaluation, logical frameworks
- **Use when**: Users need analysis, comparisons, evaluations, or research assistance

### Step 2B: Creating Your Own LLM Implementation

If you prefer to use your own custom LLM model instead of the NeuraX family, create a class that extends `BaseLLMService` and implements the abstract methods:

```python
from app.core.llm_service import BaseLLMService, LLMMessage, LLMResponse
from typing import List, Dict, Any, Optional, AsyncGenerator
import asyncio

class YourCustomLLMService(BaseLLMService):
    def __init__(self, model_name: str = "your-custom-model"):
        super().__init__(model_name)
        # Initialize your LLM here
        # Example:
        # self.model = load_your_model("/path/to/model")
        # self.tokenizer = load_your_tokenizer("/path/to/tokenizer")

    async def generate_response(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Implement your LLM inference logic here.
        
        Args:
            messages: Conversation history in chronological order
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse: The generated response
        """
        # 1. Preprocess messages for your model
        formatted_prompt = self._format_messages_for_model(messages)
        
        # 2. Run inference
        raw_output = await self._run_inference(
            formatted_prompt, 
            temperature=temperature,
            max_length=max_tokens
        )
        
        # 3. Postprocess output
        response_text = self._postprocess_output(raw_output)
        
        # 4. Determine response type (optional)
        response_type = self._detect_response_type(response_text)
        
        # 5. Calculate metrics
        tokens_used = self._calculate_tokens_used(raw_output)
        
        return LLMResponse(
            content=response_text,
            message_type=response_type,
            metadata={
                "custom_metric": "your_value",
                "processing_time_ms": 123
            },
            model_name=self.model_name,
            tokens_used=tokens_used
        )

    async def generate_response_stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Implement streaming response generation.
        Yield chunks of the response as they become available.
        """
        # Implement your streaming logic here
        # For example, if your model supports streaming:
        async for chunk in self._stream_inference(
            self._format_messages_for_model(messages),
            temperature=temperature,
            max_length=max_tokens
        ):
            yield chunk

    # Helper methods (customize as needed)
    def _format_messages_for_model(self, messages: List[LLMMessage]) -> str:
        """Convert LLMMessage objects to your model's expected input format"""
        # Implement your formatting logic
        pass
    
    async def _run_inference(self, prompt: str, **kwargs) -> str:
        """Run your model inference"""
        # Implement your inference logic
        pass
    
    def _postprocess_output(self, raw_output: str) -> str:
        """Process raw model output"""
        # Implement your postprocessing
        pass
    
    def _detect_response_type(self, text: str) -> LLMMessageType:
        """Detect if response should be text, code, image, etc."""
        # Implement your logic
        return LLMMessageType.TEXT
    
    def _calculate_tokens_used(self, raw_output: str) -> int:
        """Calculate number of tokens used"""
        # Implement your token counting
        return len(raw_output.split())  # Placeholder
```

### Step 3: Update the Factory Function (For Custom Models)

If you're using your own custom LLM implementation, modify the `get_llm_service()` function in `/backend/app/core/llm_service.py` to return your implementation:

```python
def get_llm_service(model_variant: str = "base") -> BaseLLMService:
    """
    Factory function to get the LLM service instance.
    Users can specify which NeuraX variant to use, or provide their own implementation.

    Args:
        model_variant: Which NeuraX variant to use ("base", "code", "creative", "analysis")
                      or "custom" for user-defined implementation

    Returns:
        BaseLLMService: An instance of the LLM service to use
    """
    # Map variant names to classes
    variant_map = {
        "base": NeuraXBase,
        "code": NeuraXCode,
        "creative": NeuraXCreative,
        "analysis": NeuraXAnalysis,
        "custom": YourCustomLLMService  # Replace with your custom class
    }

    # Get the appropriate class
    service_class = variant_map.get(model_variant.lower(), NeuraXBase)

    # Return the appropriate instance
    if model_variant.lower() == "custom":
        # For custom implementations, use your model name
        return service_class(model_name="your-model-name")
    else:
        # For NeuraX variants, use the appropriate model name
        return service_class()
```

For NeuraX variants, you can also specify a custom model name if needed:
```python
# Get NeuraX Code with custom model name
llm_service = NeuraXCode(model_name="neurax-code-v2")
```

### Step 4: Configure Your Model

Depending on your LLM choice, you may need to:

#### For NeuraX Family (Built-in Examples):
No additional configuration needed - these are example implementations showing the pattern.
In production, you would replace the placeholder logic with your actual NeuraX models.

#### For Custom LLM Implementations:
1. **Place model files** in an accessible location
2. **Set environment variables** for configuration (API keys, paths, etc.)
3. **Install required dependencies** in `requirements.txt` or `requirements-dev.txt`
4. **Ensure proper GPU/CPU access** if needed

Example environment variables you might need:
```bash
# In your backend/.env file
LLM_MODEL_PATH=/path/to/your/model
LLM_MODEL_TYPE=gguf  # or pytorch, tensorflow, etc.
LLM_CONTEXT_LENGTH=4096
LLM_BATCH_SIZE=8
NEURAX_VARIANT=code  # Optional: set default variant
```

### Step 5: Test Your Integration

1. **Restart the backend service** to load your LLM implementation
2. **Test the chat endpoint** with a simple message
3. **Check logs** for any initialization or inference errors
4. **Verify responses** are coming from your selected model/variant

## Using Different Variants in Your Application

You can dynamically switch between NeuraX variants based on user input or context:

```python
from app.core.llm_service import get_llm_service
from app.core.config import settings

def get_appropriate_llm_service(user_message: str) -> BaseLLMService:
    """Automatically select the best NeuraX variant based on user input"""
    
    # Code-related keywords
    code_keywords = ["code", "program", "function", "class", "algorithm", "debug", 
                    "python", "javascript", "java", "cpp", "sql", "html", "css"]
    
    # Creative-related keywords
    creative_keywords = ["story", "creative", "imagine", "design", "brainstorm", "idea",
                        "novel", "poem", "song", "character", "plot", "setting"]
    
    # Analysis-related keywords
    analysis_keywords = ["analyze", "analysis", "data", "statistics", "research", "compare",
                        "evaluate", "assess", "calculate", "reason", "logic", "problem"]
    
    user_message_lower = user_message.lower()
    
    # Check for code requests
    if any(keyword in user_message_lower for keyword in code_keywords):
        return get_llm_service("code")
    
    # Check for creative requests
    elif any(keyword in user_message_lower for keyword in creative_keywords):
        return get_llm_service("creative")
    
    # Check for analysis requests
    elif any(keyword in user_message_lower for keyword in analysis_keywords):
        return get_llm_service("analysis")
    
    # Default to base for general conversation
    else:
        return get_llm_service("base")
```

## Supported Features

Your LLM (whether NeuraX variant or custom) can handle:

- **Text conversations** (standard Q&A)
- **Code generation** (when prompted appropriately)
- **Image description requests** (for multimodal models)
- **File analysis** (if your model supports it)
- **Contextual conversations** (using chat history from Redis)
- **Streaming responses** (if you implement the streaming method)
- **Dynamic variant selection** (based on input analysis)

## Performance Considerations

1. **Model Loading**: Load your model once during service initialization, not per request
2. **Concurrency**: Ensure your model can handle multiple concurrent requests
3. **Memory Usage**: Monitor VRAM/RAM usage, especially for large models
4. **Batching**: Consider batching requests if your model supports it
5. **Caching**: Implement response caching for common queries if appropriate
6. **Variant Switching**: Minimize overhead when switching between NeuraX variants

## Troubleshooting

### Common Issues

1. **Model not loading**: Check file paths and permissions
2. **Out of memory**: Reduce batch size or use model quantization
3. **Slow response**: Optimize model inference or use hardware acceleration
4. **Incorrect responses**: Verify your preprocessing/postprocessing logic
5. **Dependency conflicts**: Ensure compatible versions of ML libraries
6. **Variant confusion**: Ensure you're selecting the appropriate variant for the task

### Debugging Tips

1. Start with the `ExampleLLMService` to verify the framework works
2. Add logging to your implementation to see what's being passed in/out
3. Test your LLM independently before integrating
4. Check the backend logs for detailed error messages
5. Verify the `get_llm_service()` function is actually returning your instance
6. Test variant selection logic with various inputs

## Example Implementations

### For Hugging Face Transformers
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

class HuggingFaceLLMService(BaseLLMService):
    def __init__(self, model_path: str, model_name: str = "hf-llm"):
        super().__init__(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto"
        )
    
    # Implement generate_response using self.model.generate()
```

### For llama.cpp (GGUF models)
```python
from llama_cpp import Llama

class LlamaCPPLLMService(BaseLLMService):
    def __init__(self, model_path: str, model_name: str = "llama-cpp"):
        super().__init__(model_name)
        self.llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=6,
            n_gpu_layers=35  # Adjust based on your GPU
        )
    
    # Implement generate_response using self.llm()
```

### For Local API Server (like text-generation-webui)
```python
import httpx

class APILLMService(BaseLLMService):
    def __init__(self, api_url: str, model_name: str = "api-llm"):
        super().__init__(model_name)
        self.api_url = api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def generate_response(self, messages, **kwargs):
        # Convert messages to API format and POST to your endpoint
        pass
```

## Next Steps

After integrating your LLM:

1. **Consider updating other AI endpoints** (agents, search, image) to use your LLM
2. **Add advanced features** like:
   - Tool usage integration (for agents)
   - Retrieval-Augmented Generation (RAG) for search
   - Multimodal capabilities (for image understanding)
   - Fine-tuning capabilities
3. **Implement monitoring** and analytics for your LLM usage
4. **Add safety features** like content filtering and rate limiting
5. **Consider model versioning** and A/B testing capabilities
6. **Create domain-specific variants** (e.g., NeuraX-Medical, NeuraX-Legal)

## Support

If you need help with your specific LLM implementation, refer to:
- Your model's documentation
- The framework/library documentation you're using
- The example implementation in `ExampleLLMService` as a starting point
- The NeuraX family implementations in `llm_service.py` as patterns to follow
- The NovaMind AI architecture documentation