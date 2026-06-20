"""
Demo script showing how to use the NeuraX LLM family with NovaMind AI
"""

import asyncio
from app.core.llm_service import (
    NeuraXBase,
    NeuraXCode,
    NeuraXCreative,
    NeuraXAnalysis,
    get_llm_service,
    LLMMessage,
    LLMMessageType
)

async def demo_neurax_family():
    """Demonstrate all NeuraX variants"""

    print("=== NeuraX LLM Family Demo ===\n")

    # Test NeuraX Base (General Purpose)
    print("1. NeuraX-Base (General Purpose)")
    base_llm = NeuraXBase(model_name="NeuraX-Base-Demo")
    messages = [
        LLMMessage(
            content="Hello, how are you today?",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]
    response = await base_llm.generate_response(messages)
    print(f"Response: {response.content[:100]}...")
    print(f"Model: {response.model_name}, Type: {response.message_type.value}\n")

    # Test NeuraX Code (Programming Specialist)
    print("2. NeuraX-Code (Programming Specialist)")
    code_llm = NeuraXCode(model_name="NeuraX-Code-Demo")
    messages = [
        LLMMessage(
            content="Write a Python function to check if a number is prime",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]
    response = await code_llm.generate_response(messages)
    print(f"Response: {response.content[:100]}...")
    print(f"Model: {response.model_name}, Type: {response.message_type.value}\n")

    # Test NeuraX Creative (Writing Specialist)
    print("3. NeuraX-Creative (Writing Specialist)")
    creative_llm = NeuraXCreative(model_name="NeuraX-Creative-Demo")
    messages = [
        LLMMessage(
            content="Write a short poem about artificial intelligence",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]
    response = await creative_llm.generate_response(messages)
    print(f"Response: {response.content[:100]}...")
    print(f"Model: {response.model_name}, Type: {response.message_type.value}\n")

    # Test NeuraX Analysis (Reasoning Specialist)
    print("4. NeuraX-Analysis (Reasoning Specialist)")
    analysis_llm = NeuraXAnalysis(model_name="NeuraX-Analysis-Demo")
    messages = [
        LLMMessage(
            content="Analyze the advantages and disadvantages of renewable energy",
            message_type=LLMMessageType.TEXT,
            is_ai=False,
            user_id=1
        )
    ]
    response = await analysis_llm.generate_response(messages)
    print(f"Response: {response.content[:100]}...")
    print(f"Model: {response.model_name}, Type: {response.message_type.value}\n")

    # Test Factory Function
    print("5. Factory Function Demo")
    llm_service = get_llm_service("code")
    print(f"Got LLM service: {type(llm_service).__name__}")
    print(f"Model name: {llm_service.model_name}")

    # Test dynamic variant selection
    print("\n6. Dynamic Variant Selection")

    def get_appropriate_llm_service(user_message: str):
        """Automatically select the best NeuraX variant based on user input"""
        code_keywords = ["code", "program", "function", "class", "algorithm", "debug"]
        creative_keywords = ["story", "creative", "imagine", "design", "brainstorm", "idea", "poem"]
        analysis_keywords = ["analyze", "analysis", "data", "statistics", "research", "compare"]

        user_message_lower = user_message.lower()

        if any(keyword in user_message_lower for keyword in code_keywords):
            return get_llm_service("code")
        elif any(keyword in user_message_lower for keyword in creative_keywords):
            return get_llm_service("creative")
        elif any(keyword in user_message_lower for keyword in analysis_keywords):
            return get_llm_service("analysis")
        else:
            return get_llm_service("base")

    test_messages = [
        "Write a JavaScript function to sort an array",
        "Tell me a story about a dragon",
        "Analyze the impact of social media on society",
        "What's the weather like today?"
    ]

    for msg in test_messages:
        llm = get_appropriate_llm_service(msg)
        print(f"'{msg}' -> {type(llm).__name__} ({llm.model_name})")

    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    asyncio.run(demo_neurax_family())