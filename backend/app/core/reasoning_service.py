"""
Advanced reasoning techniques for LLM enhancement
Implements various reasoning strategies to improve LLM performance
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)

class ReasoningStrategy(Enum):
    """Different reasoning strategies available"""
    CHAIN_OF_THOUGHT = "chain_of_thought"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    SELF_CONSISTENCY = "self_consistency"
    DEBATE = "debate"
    REFLECTION = "reflection"
    REFINEMENT = "refinement"

@dataclass
class ReasoningResult:
    """Result from a reasoning process"""
    strategy: ReasoningStrategy
    final_answer: str
    reasoning_steps: List[Dict[str, Any]]
    confidence: float
    metadata: Dict[str, Any]

class ReasoningService:
    """Service for applying advanced reasoning techniques to LLM outputs"""

    def __init__(self, llm_service):
        """
        Initialize with an LLM service

        Args:
            llm_service: An instance of BaseLLMService or compatible
        """
        self.llm_service = llm_service

    async def chain_of_thought(self, prompt: str, **llm_kwargs) -> ReasoningResult:
        """
        Apply chain-of-thought reasoning
        Encourages the model to break down problems into steps
        """
        cot_prompt = f"""{prompt}

Let's think step by step.
Provide your reasoning in clear steps, then give your final answer."""

        try:
            response = await self.llm_service.generate_response(
                [{"content": cot_prompt, "message_type": "text", "is_ai": False}],
                **llm_kwargs
            )

            # Parse the response to extract reasoning steps and final answer
            # This is a simplified parser - in production would be more sophisticated
            content = response.content
            lines = content.split('\n')

            reasoning_steps = []
            final_answer = content

            # Look for common step indicators
            step_indicators = ['step', 'first', 'second', 'third', 'next', 'then', 'therefore', 'thus']
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                if any(indicator in line_lower for indicator in step_indicators) and len(line.strip()) > 10:
                    reasoning_steps.append({
                        "step": len(reasoning_steps) + 1,
                        "text": line.strip(),
                        "type": "reasoning_step"
                    })

            # Assume the last substantial paragraph is the final answer
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            if paragraphs:
                final_answer = paragraphs[-1]

            return ReasoningResult(
                strategy=ReasoningStrategy.CHAIN_OF_THOUGHT,
                final_answer=final_answer,
                reasoning_steps=reasoning_steps,
                confidence=0.85,  # Placeholder - would be calculated based on consistency
                metadata={
                    "original_prompt": prompt,
                    "model_used": response.model_name,
                    "tokens_used": response.tokens_used
                }
            )
        except Exception as e:
            logger.error(f"Error in chain-of-thought reasoning: {str(e)}")
            raise

    async def tree_of_thoughts(self, prompt: str, breadth: int = 3, depth: int = 2,
                             **llm_kwargs) -> ReasoningResult:
        """
        Apply tree-of-thoughts reasoning
        Explores multiple reasoning paths at each step
        """
        try:
            # This is a simplified implementation
            # In production, this would implement a proper tree search

            # Generate multiple initial thoughts
            thoughts_prompt = f"""{prompt}

Generate {breadth} different approaches to think about this problem.
For each approach, provide a brief description of how you would tackle it."""

            thoughts_response = await self.llm_service.generate_response(
                [{"content": thoughts_prompt, "message_type": "text", "is_ai": False}],
                **llm_kwargs
            )

            # Extract the different approaches (simplified)
            approaches = []
            content = thoughts_response.content
            # Split by common delimiters
            sections = content.split('\n\n')
            for i, section in enumerate(sections[:breadth]):
                if section.strip():
                    approaches.append({
                        "id": i,
                        "description": section.strip(),
                        "thoughts": []
                    })

            # For each approach, develop the thought further
            final_thoughts = []
            for approach in approaches:
                develop_prompt = f"""{prompt}

Approach: {approach['description']}

Develop this approach further with detailed reasoning steps.
Then provide a conclusion based on this approach."""

                develop_response = await self.llm_service.generate_response(
                    [{"content": develop_prompt, "message_type": "text", "is_ai": False}],
                    **llm_kwargs
                )

                approach["thoughts"] = [{
                    "step": 1,
                    "text": develop_response.content,
                    "type": "developed_thought"
                }]

                final_thoughts.append(approach)

            # Synthesize the best approach (simplified - would evaluate each)
            synthesis_prompt = f"""{prompt}

Based on these different approaches:
{chr(10).join([f"- {a['description']}" for a in approaches])}

Synthesize the best insights from these approaches into a final answer."""

            synthesis_response = await self.llm_service.generate_response(
                [{"content": synthesis_prompt, "message_type": "text", "is_ai": False}],
                **llm_kwargs
            )

            return ReasoningResult(
                strategy=ReasoningStrategy.TREE_OF_THOUGHTS,
                final_answer=synthesis_response.content,
                reasoning_steps=[
                    {"phase": "approach_generation", "approaches": len(approaches)},
                    {"phase": "thought_development", "developed": len(final_thoughts)},
                    {"phase": "synthesis", "result": "synthesized_answer"}
                ],
                confidence=0.88,
                metadata={
                    "original_prompt": prompt,
                    "breadth": breadth,
                    "depth": depth,
                    "model_used": synthesis_response.model_name,
                    "tokens_used": synthesis_response.tokens_used
                }
            )
        except Exception as e:
            logger.error(f"Error in tree-of-thoughts reasoning: {str(e)}")
            raise

    async def self_consistency(self, prompt: str, num_samples: int = 5,
                             **llm_kwargs) -> ReasoningResult:
        """
        Apply self-consistency reasoning
        Samples multiple reasoning paths and selects the most consistent answer
        """
        try:
            # Generate multiple responses
            responses = []
            for i in range(num_samples):
                response = await self.llm_service.generate_response(
                    [{"content": prompt, "message_type": "text", "is_ai": False}],
                    **llm_kwargs
                )
                responses.append(response)

            # Extract answers from responses
            answers = [r.content.strip() for r in responses]

            # Find the most common answer (simplified - in production would use semantic similarity)
            # For now, we'll just use the first answer and note consistency
            most_common_answer = answers[0] if answers else ""

            # Calculate consistency as percentage of identical answers
            identical_count = sum(1 for a in answers if a == most_common_answer)
            consistency_ratio = identical_count / len(answers) if answers else 0

            return ReasoningResult(
                strategy=ReasoningStrategy.SELF_CONSISTENCY,
                final_answer=most_common_answer,
                reasoning_steps=[
                    {"phase": "sampling", "samples": num_samples},
                    {"phase": "consistency_check", "identical": identical_count, "total": num_samples},
                    {"phase": "selection", "method": "most_frequent"}
                ],
                confidence=0.7 + (consistency_ratio * 0.3),  # Scale confidence by consistency
                metadata={
                    "original_prompt": prompt,
                    "num_samples": num_samples,
                    "answers": answers,
                    "consistency_ratio": consistency_ratio,
                    "model_used": responses[0].model_name if responses else "unknown",
                    "total_tokens_used": sum(r.tokens_used or 0 for r in responses)
                }
            )
        except Exception as e:
            logger.error(f"Error in self-consistency reasoning: {str(e)}")
            raise

    async def debate(self, prompt: str, num_agents: int = 3,
                   rounds: int = 2, **llm_kwargs) -> ReasoningResult:
        """
        Apply debate reasoning
        Multiple AI agents debate to arrive at a better answer
        """
        try:
            # Initialize agents with different perspectives
            perspectives = [
                "analytical and logical",
                "creative and intuitive",
                "practical and pragmatic",
                "skeptical and questioning",
                "optimistic and hopeful"
            ][:num_agents]

            # Store each agent's thoughts across rounds
            agent_thoughts = {i: [] for i in range(num_agents)}

            # Conduct debate rounds
            for round_num in range(rounds):
                for agent_id in range(num_agents):
                    perspective = perspectives[agent_id % len(perspectives)]

                    # Build context from previous rounds
                    context = ""
                    if round_num > 0:
                        context = "Previous discussion:\n"
                        for other_id in range(num_agents):
                            if other_id != agent_id:
                                last_thought = agent_thoughts[other_id][-1] if agent_thoughts[other_id] else ""
                                context += f"Agent {other_id} ({perspectives[other_id % len(perspectives)]}): {last_thought.get('text', '')}\n"

                    debate_prompt = f"""{prompt}

You are Agent {agent_id} with a {perspective} perspective.

{context}
Provide your perspective on this issue. Respond to previous points if relevant, then state your position."""

                    response = await self.llm_service.generate_response(
                        [{"content": debate_prompt, "message_type": "text", "is_ai": False}],
                        **llm_kwargs
                    )

                    agent_thoughts[agent_id].append({
                        "round": round_num,
                        "perspective": perspective,
                        "text": response.content,
                        "type": "debate_contribution"
                    })

            # Synthesize final answer from the debate
            synthesis_prompt = f"""{prompt}

A debate was conducted with {num_agents} agents over {rounds} rounds.
Each agent had a different perspective: {', '.join(perspectives)}.

Based on the debate, provide a synthesized final answer that integrates the best insights from all perspectives."""

            debate_history = ""
            for agent_id in range(num_agents):
                perspective = perspectives[agent_id % len(perspectives)]
                debate_history += f"Agent {agent_id} ({perspective}):\n"
                for thought in agent_thoughts[agent_id]:
                    debate_history += f"  Round {thought['round']}: {thought['text'][:100]}...\n"
                debate_history += "\n"

            synthesis_prompt_with_history = f"""{prompt}

Debate History:
{debate_history}

Based on the above debate, provide a synthesized final answer."""

            synthesis_response = await self.llm_service.generate_response(
                [{"content": synthesis_prompt_with_history, "message_type": "text", "is_ai": False}],
                **llm_kwargs
            )

            return ReasoningResult(
                strategy=ReasoningStrategy.DEBATE,
                final_answer=synthesis_response.content,
                reasoning_steps=[
                    {"phase": "initialization", "agents": num_agents, "perspectives": perspectives},
                    {"phase": "debate_rounds", "rounds": rounds},
                    {"phase": "synthesis", "participants": [f"Agent {i} ({p})" for i, p in enumerate(perspectives)]}
                ],
                confidence=0.82,
                metadata={
                    "original_prompt": prompt,
                    "num_agents": num_agents,
                    "rounds": rounds,
                    "perspectives": perspectives,
                    "debate_history": debate_history,
                    "model_used": synthesis_response.model_name,
                    "tokens_used": synthesis_response.tokens_used
                }
            )
        except Exception as e:
            logger.error(f"Error in debate reasoning: {str(e)}")
            raise

    async def reflection(self, prompt: str, **llm_kwargs) -> ReasoningResult:
        """
        Apply reflection reasoning
        Model critiques and improves its own reasoning
        """
        try:
            # First, generate an initial answer
            initial_response = await self.llm_service.generate_response(
                [{"content": prompt, "message_type": "text", "is_ai": False}],
                **llm_kwargs
            )

            # Then, ask the model to critique its own answer
            critique_prompt = f"""{prompt}

Initial answer:
{initial_response.content}

Critically evaluate this answer. Identify any errors, omissions, or areas for improvement.
Provide specific feedback on how to make it better."""

            critique_response = await self.llm_service.generate_response(
                [{"content": critique_prompt, "message_type": "text", "is_ai": False}],
                **llm_kwargs
            )

            # Finally, generate an improved answer based on the critique
            refinement_prompt = f"""{prompt}

Initial answer:
{initial_response.content}

Critique of initial answer:
{critique_response.content}

Please provide an improved answer that addresses the criticisms while maintaining correctness."""

            refined_response = await self.llm_service.generate_response(
                [{"content": refinement_prompt, "message_type": "text", "is_ai": False}],
                **llm_kwargs
            )

            return ReasoningResult(
                strategy=ReasoningStrategy.REFLECTION,
                final_answer=refined_response.content,
                reasoning_steps=[
                    {"phase": "initial_answer", "answer": initial_response.content[:100] + "..."},
                    {"phase": "self_critique", "critique": critique_response.content[:100] + "..."},
                    {"phase": "refined_answer", "answer": refined_response.content[:100] + "..."}
                ],
                confidence=0.8,
                metadata={
                    "original_prompt": prompt,
                    "initial_model": initial_response.model_name,
                    "critique_model": critique_response.model_name,
                    "refined_model": refined_response.model_name,
                    "initial_tokens": initial_response.tokens_used,
                    "critique_tokens": critique_response.tokens_used,
                    "refined_tokens": refined_response.tokens_used
                }
            )
        except Exception as e:
            logger.error(f"Error in reflection reasoning: {str(e)}")
            raise

    async def refinement(self, prompt: str, iterations: int = 2,
                       **llm_kwargs) -> ReasoningResult:
        """
        Apply iterative refinement
        Repeatedly improve the answer through self-refinement
        """
        try:
            current_answer = ""
            reasoning_steps = []

            for i in range(iterations):
                if i == 0:
                    # First iteration: generate initial answer
                    prompt_to_use = prompt
                    step_name = "initial_generation"
                else:
                    # Subsequent iterations: refine based on previous answer
                    prompt_to_use = f"""{prompt}

Previous answer:
{current_answer}

Please improve and refine this answer. Make it more accurate, complete, and well-structured."""
                    step_name = f"refinement_iteration_{i}"

                response = await self.llm_service.generate_response(
                    [{"content": prompt_to_use, "message_type": "text", "is_ai": False}],
                    **llm_kwargs
                )

                current_answer = response.content
                reasoning_steps.append({
                    "phase": step_name,
                    "iteration": i + 1,
                    "answer_preview": current_answer[:100] + "..." if len(current_answer) > 100 else current_answer,
                    "model_used": response.model_name,
                    "tokens_used": response.tokens_used
                })

            return ReasoningResult(
                strategy=ReasoningStrategy.REFINEMENT,
                final_answer=current_answer,
                reasoning_steps=reasoning_steps,
                confidence=0.75 + (iterations * 0.05),  # Slightly increase confidence with iterations
                metadata={
                    "original_prompt": prompt,
                    "iterations": iterations,
                    "final_model": reasoning_steps[-1]["model_used"] if reasoning_steps else "unknown",
                    "total_tokens_used": sum(step.get("tokens_used", 0) for step in reasoning_steps)
                }
            )
        except Exception as e:
            logger.error(f"Error in refinement reasoning: {str(e)}")
            raise

    async def apply_reasoning(self, prompt: str, strategy: ReasoningStrategy = ReasoningStrategy.CHAIN_OF_THOUGHT,
                            **kwargs) -> ReasoningResult:
        """
        Apply a specified reasoning strategy

        Args:
            prompt: The input prompt/reasoning task
            strategy: The reasoning strategy to apply
            **kwargs: Additional arguments passed to the specific reasoning method
                     (and subsequently to the LLM service)

        Returns:
            ReasoningResult containing the outcome
        """
        strategy_map = {
            ReasoningStrategy.CHAIN_OF_THOUGHT: self.chain_of_thought,
            ReasoningStrategy.TREE_OF_THOUGHTS: self.tree_of_thoughts,
            ReasoningStrategy.SELF_CONSISTENCY: self.self_consistency,
            ReasoningStrategy.DEBATE: self.debate,
            ReasoningStrategy.REFLECTION: self.reflection,
            ReasoningStrategy.REFINEMENT: self.refinement
        }

        if strategy not in strategy_map:
            raise ValueError(f"Unsupported reasoning strategy: {strategy}")

        # Extract LLM-specific kwargs vs reasoning-specific kwargs
        # For simplicity, we'll pass all kwargs to both levels
        # In production, we might want to separate these more carefully
        llm_kwargs = {k: v for k, v in kwargs.items()
                     if k in ['temperature', 'max_tokens', 'top_p', 'stop']}
        reasoning_kwargs = {k: v for k, v in kwargs.items()
                           if k not in ['temperature', 'max_tokens', 'top_p', 'stop']}

        # Merge them, with llm_kwargs taking precedence for overlapping keys
        final_kwargs = {**reasoning_kwargs, **llm_kwargs}

        return await strategy_map[strategy](prompt, **final_kwargs)

# Convenience function
async def apply_reasoning(llm_service, prompt: str, strategy: ReasoningStrategy = ReasoningStrategy.CHAIN_OF_THOUGHT,
                         **kwargs) -> ReasoningResult:
    """
    Convenience function to apply reasoning techniques
    """
    reasoning_service = ReasoningService(llm_service)
    return await reasoning_service.apply_reasoning(prompt, strategy, **kwargs)