import json
import os
from typing import Dict, Any, List

from langchain_openai import ChatOpenAl
from langfuse.decorators import observe

# Import the global Langfuse configuration from your config directory
from config.langfuse_settings import langfuse_config

class QualityGateSystem:
    """
    An enhanced LLM-as-a-Judge system for validating and improving agent responses.
    This class handles all quality assurance logic, including agent response quality,
    RAG groundedness, and RAG relevance, for the multi-agent workflow.
    """

    def __init__(self):
        """Initializes the Quality Gate System."""
        # Initialize the LLM client used for all evaluation tasks.
        # Temperature is set to 0 for consistent, objective outputs.
        self.evaluator_llm = ChatOpenAl(
            model="gpt-4o",
            temperature=0,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Use the already initialized Langfuse client from the global config.
        self.langfuse = langfuse_config.client

    @observe()
    async def validate_response(self, query: str, response: str, agent_type: str) -> Dict[str, Any]:
        """
        Validates an agent's response using a detailed, LLM-based evaluation.

        This method checks the response against specific criteria defined in the Langfuse
        configuration and logs the results for observability.

        Args:
            query: The original user query.
            response: The agent's generated response.
            agent_type: The type of agent (e.g., "incident_response") being evaluated.

        Returns:
            A dictionary containing the evaluation result, including a pass/fail status,
            scores, and feedback.
        """
        evaluator_config = langfuse_config.create_agent_evaluator(agent_type)
        evaluation_prompt = f"""
You are an expert cybersecurity evaluator. Your task is to evaluate the following response with strict objectivity.

**Original Query:**
{query}

**Agent Type:**
{agent_type}

**Agent Response to Evaluate:**
{response}

---
**Evaluation Criteria:**
{evaluator_config['prompt']}

**Instructions:**
Be thorough and critical. Specifically, assess the response for technical accuracy, completeness, actionability, and appropriate tone.
Return **only a valid JSON object** in the specified format. Do not add any commentary outside the JSON structure.
"""
        try:
            evaluation = await self.evaluator_llm.ainvoke(evaluation_prompt)
            result = json.loads(evaluation.content)

            if not all(field in result for field in ["scores", "overall", "feedback"]):
                raise ValueError("LLM response is missing required evaluation fields.")

            self.langfuse.score(
                name=f"{agent_type}_quality_score",
                value=result.get("overall", 0.0),
                comment=result.get("feedback", "No feedback provided.")
            )
            passed = result.get("overall", 0.0) >= evaluator_config["threshold"]
            return {
                "passed": passed, "scores": result.get("scores", {}),
                "overall_score": result.get("overall", 0.0), "feedback": result.get("feedback", ""),
                "agent_type": agent_type, "threshold": evaluator_config["threshold"]
            }

        except Exception as e:
            print(f"Error during quality validation for {agent_type}: {e}")
            self.langfuse.score(
                name=f"{agent_type}_quality_error",
                value=0.0, comment=f"Quality evaluation process failed: {str(e)}"
            )
            return {
                "passed": True, "scores": {"error": 1}, "overall_score": 5.0,
                "feedback": f"Quality evaluation could not be performed due to an error: {str(e)}",
                "agent_type": agent_type, "error": str(e)
            }

    @observe()
    async def enhance_response(self, query: str, response: str, feedback: str) -> str:
        """
        Improves a response that failed the quality gate, based on specific feedback.
        """
        enhancement_prompt = f"""
You are an expert cybersecurity advisor tasked with improving a team member's work. Improve the following response based on the specific quality issues identified.

**Original Query:**
{query}

**Original Response (needs improvement):**
{response}

---
**Quality Issues to Address:**
{feedback}

---
**Your Instructions:**
1. Address **all** specific issues mentioned in the feedback.
2. Maintain the valuable aspects of the original response.
3. Ensure the final answer is technically accurate, complete, and actionable.
4. Preserve a professional tone and appropriate level of expertise.

Provide only the improved, final response.
"""
        try:
            enhanced = await self.evaluator_llm.ainvoke(enhancement_prompt)
            self.langfuse.score(
                name="response_enhancement_successful", value=1.0,
                comment="Response was successfully enhanced after failing quality gate."
            )
            return enhanced.content
        
        except Exception as e:
            print(f"Error during response enhancement: {e}")
            self.langfuse.score(
                name="response_enhancement_failed", value=0.0,
                comment=f"Response enhancement failed: {str(e)}"
            )
            return response

    @observe()
    async def check_groundedness(self, answer: str, context_chunks: List[str]) -> Dict[str, Any]:
        """
        Checks if the answer is factually supported by the retrieved context (RAG).
        """
        full_context = "\n---\n".join(context_chunks)
        prompt = f"""
You are a meticulous fact-checker. Your task is to determine if the following statement is fully supported by the provided context.

**Context:**
{full_context}

---
**Statement to Verify:**
{answer}

---
**Instructions:**
Compare the statement against the context. The statement must be directly and explicitly supported by the context. Respond with only a valid JSON object in the following format:
{{
    "grounded": <true or false>,
    "reason": "<A brief explanation for your decision>"
}}
"""
        try:
            evaluation = await self.evaluator_llm.ainvoke(prompt)
            result = json.loads(evaluation.content)
            
            self.langfuse.score(
                name="rag_groundedness", value=1 if result.get("grounded") else 0,
                comment=result.get("reason", "No reason provided.")
            )
            return result
        except Exception as e:
            print(f"Error during groundedness check: {e}")
            return {"grounded": False, "reason": f"Evaluation failed: {e}"}

    @observe()
    async def check_relevance(self, query: str, context_chunks: List[str]) -> Dict[str, Any]:
        """
        Checks if the retrieved context chunks are relevant to the user's query (RAG).
        """
        full_context = "\n---\n".join(context_chunks)
        prompt = f"""
You are a relevance assessor. Your task is to determine if the provided context is relevant for answering the user's query.

**User Query:**
{query}

---
**Context to Evaluate:**
{full_context}

---
**Instructions:**
Evaluate how relevant the context is for forming a comprehensive answer to the user's query. Respond with only a valid JSON object in the following format:
{{
    "relevant": <true or false>,
    "score": <A relevance score from 1 (not relevant) to 10 (highly relevant)>,
    "reason": "<A brief explanation for your decision>"
}}
"""
        try:
            evaluation = await self.evaluator_llm.ainvoke(prompt)
            result = json.loads(evaluation.content)
            
            self.langfuse.score(
                name="rag_relevance", value=result.get("score", 0),
                comment=result.get("reason", "No reason provided.")
            )
            return result
        except Exception as e:
            print(f"Error during relevance check: {e}")
            return {"relevant": False, "score": 0, "reason": f"Evaluation failed: {e}"}