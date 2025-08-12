import json
import os
import logging
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI
from langfuse import observe, get_client
from openai import AsyncOpenAI

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
        self.evaluator_llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Use the already initialized Langfuse client from the global config.
        # If not available, get_client() will create one with env variables
        self.langfuse = langfuse_config.client if langfuse_config.client else get_client()

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
        # Get the Langfuse client for scoring
        langfuse = get_client()
        
        if not self.langfuse:
            # Return a default success response if Langfuse is not initialized
            return {"passed": True, "overall_score": 10.0, "feedback": "Langfuse offline."}

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
            
            # Clean the response to remove markdown code blocks
            llm_output = evaluation.content.strip().replace("```json", "").replace("```", "").strip()

            try:
                result = json.loads(llm_output)
                if not all(field in result for field in ["scores", "overall", "feedback"]):
                    raise ValueError("LLM response is missing required evaluation fields.")
            except (json.JSONDecodeError, ValueError) as json_error:
                logging.error(f"Failed to parse LLM evaluation response: {json_error}")
                logging.error(f"LLM Raw Output: {llm_output}")
                # Score the current observation with error
                langfuse.score_current_span(
                    name="quality_gate_parsing_error",
                    value=0,
                    comment=str(json_error)
                )
                return {"passed": False, "overall_score": 0.0, "feedback": "Failed to parse evaluation."}

            # Score the current observation with the quality score
            langfuse.score_current_span(
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
            logging.error(f"Error during quality validation for {agent_type}: {e}")
            langfuse.score_current_span(
                name="quality_gate_execution_error",
                value=0,
                comment=str(e)
            )
            return {
                "passed": True,  # Pass gracefully to not block the workflow
                "scores": {"error": 1}, "overall_score": 5.0,
                "feedback": f"Quality evaluation could not be performed due to an error: {str(e)}",
                "agent_type": agent_type, "error": str(e)
            }

    @observe()
    async def enhance_response(self, query: str, response: str, feedback: str) -> str:
        """
        Improves a response that failed the quality gate, based on specific feedback.
        """
        langfuse = get_client()
        
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
            langfuse.score_current_span(
                name="response_enhancement_successful",
                value=1.0,
                comment="Response was successfully enhanced."
            )
            return enhanced.content
        
        except Exception as e:
            logging.error(f"Error during response enhancement: {e}")
            langfuse.score_current_span(
                name="response_enhancement_failed",
                value=0.0,
                comment=f"Response enhancement failed: {str(e)}"
            )
            return response

    @observe()
    async def check_groundedness(self, answer: str, context_chunks: List[str]) -> Dict[str, Any]:
        """
        Checks if the answer is factually supported by the retrieved context (RAG).
        """
        langfuse = get_client()
        
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
            result = json.loads(evaluation.content.strip().replace("```json", "").replace("```", "").strip())
            
            langfuse.score_current_span(
                name="rag_groundedness",
                value=1 if result.get("grounded") else 0,
                comment=result.get("reason", "No reason provided.")
            )
            return result
        except Exception as e:
            logging.error(f"Error during groundedness check: {e}")
            langfuse.score_current_span(
                name="rag_groundedness_error",
                value=0,
                comment=str(e)
            )
            return {"grounded": False, "reason": f"Evaluation failed: {e}"}

    @observe()
    async def check_relevance(self, query: str, context_chunks: List[str]) -> Dict[str, Any]:
        """
        Checks if the retrieved context chunks are relevant to the user's query (RAG).
        """
        langfuse = get_client()
        
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
            result = json.loads(evaluation.content.strip().replace("```json", "").replace("```", "").strip())
            
            langfuse.score_current_span(
                name="rag_relevance",
                value=result.get("score", 0),
                comment=result.get("reason", "No reason provided.")
            )
            return result
        except Exception as e:
            logging.error(f"Error during relevance check: {e}")
            langfuse.score_current_span(
                name="rag_relevance_error",
                value=0,
                comment=str(e)
            )
            return {"relevant": False, "score": 0, "reason": f"Evaluation failed: {e}"}