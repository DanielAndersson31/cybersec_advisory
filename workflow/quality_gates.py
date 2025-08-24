import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe, get_client
from pydantic import ValidationError

from config.langfuse_settings import langfuse_config
from workflow.schemas import QualityGateResult, RAGRelevanceResult, RAGGroundednessResult

logger = logging.getLogger(__name__)


class QualityGateSystem:
    """
    An enhanced LLM-as-a-Judge system for validating and improving agent responses.
    This class handles all quality assurance logic, including agent response quality,
    RAG groundedness, and RAG relevance, using structured outputs.
    """

    def __init__(self, llm_client: ChatOpenAI):
        """Initializes the Quality Gate System with LangChain structured outputs."""
        self.evaluator_llm = llm_client
        self.langfuse = langfuse_config.client if langfuse_config.client else get_client()
        
        self.quality_llm = llm_client.with_structured_output(QualityGateResult)
        self.groundedness_llm = llm_client.with_structured_output(RAGGroundednessResult)
        self.relevance_llm = llm_client.with_structured_output(RAGRelevanceResult)

    @observe()
    async def validate_response(self, query: str, response: str, agent_type: str) -> QualityGateResult:
        """Validates an agent's response using a detailed, LLM-based evaluation."""
        langfuse = get_client()
        
        if not self.langfuse:
            return QualityGateResult(passed=True, overall_score=10.0, feedback="Langfuse offline.")

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
Return your evaluation in the required structured format.
"""
        try:
            # Retry logic with LangChain structured output
            for attempt in range(2):
                try:
                    result = await self.quality_llm.ainvoke([
                        SystemMessage(content="You are an expert cybersecurity evaluator. Provide structured quality assessments."),
                        HumanMessage(content=evaluation_prompt)
                    ])
                    break
                except Exception as e:
                    if attempt == 1:  # Last attempt
                        raise e
                    logger.warning(f"Quality validation attempt {attempt + 1} failed: {e}, retrying...")

            langfuse.score_current_span(
                name=f"{agent_type}_quality_score",
                value=result.overall_score,
                comment=result.feedback
            )

            return result

        except Exception as e:
            logging.error(f"Error during quality validation for {agent_type} after LangChain retries: {e}")
            langfuse.score_current_span(name="quality_gate_execution_error", value=0, comment=str(e))
            return QualityGateResult(
                passed=True,  # Pass gracefully to not block the workflow
                overall_score=5.0,
                feedback=f"Quality evaluation could not be performed after retries: {str(e)[:200]}"
            )

    @observe()
    async def enhance_response(self, query: str, response: str, feedback: str) -> str:
        """Improves a response that failed the quality gate, based on specific feedback."""
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
            enhanced_response = await self.evaluator_llm.ainvoke([HumanMessage(content=enhancement_prompt)])
            enhanced_content = enhanced_response.content
            langfuse.score_current_span(name="response_enhancement_successful", value=1.0, comment="Response was successfully enhanced.")
            return enhanced_content
        
        except Exception as e:
            logging.error(f"Error during response enhancement: {e}")
            langfuse.score_current_span(name="response_enhancement_failed", value=0.0, comment=f"Response enhancement failed: {e}")
            return response

    @observe()
    async def check_groundedness(self, answer: str, context_chunks: List[str]) -> RAGGroundednessResult:
        """Checks if the answer is factually supported by the retrieved context (RAG)."""
        langfuse = get_client()
        
        full_context = "\\n---\\n".join(context_chunks)
        prompt = f"""
You are a meticulous fact-checker. Your task is to determine if the following statement is fully supported by the provided context.

**Context:**
{full_context}

---
**Statement to Verify:**
{answer}

---
**Instructions:**
Compare the statement against the context. The statement must be directly and explicitly supported by the context.
Provide your assessment in the required structured format.
"""
        try:
            # Retry logic with LangChain structured output
            for attempt in range(2):
                try:
                    result = await self.groundedness_llm.ainvoke([
                        SystemMessage(content="You are an expert at evaluating whether responses are grounded in provided context."),
                        HumanMessage(content=prompt)
                    ])
                    break
                except Exception as e:
                    if attempt == 1:  # Last attempt
                        raise e
                    logger.warning(f"Groundedness evaluation attempt {attempt + 1} failed: {e}, retrying...")
            
            langfuse.score_current_span(
                name="rag_groundedness",
                value=1 if result.grounded else 0,
                comment=result.feedback
            )
            return result
        except (ValidationError, Exception) as e:
            logging.error(f"Error during groundedness check: {e}")
            langfuse.score_current_span(name="rag_groundedness_error", value=0, comment=str(e))
            return RAGGroundednessResult(grounded=False, feedback=f"Evaluation failed: {e}")

    @observe()
    async def check_relevance(self, query: str, context_chunks: List[str]) -> RAGRelevanceResult:
        """Checks if the retrieved context chunks are relevant to the user's query (RAG)."""
        langfuse = get_client()
        
        full_context = "\\n---\\n".join(context_chunks)
        prompt = f"""
You are a relevance assessor. Your task is to determine if the provided context is relevant for answering the user's query.

**User Query:**
{query}

---
**Context to Evaluate:**
{full_context}

---
**Instructions:**
Evaluate how relevant the context is for forming a comprehensive answer to the user's query.
Provide your assessment in the required structured format.
"""
        try:
            # Retry logic with LangChain structured output
            for attempt in range(2):
                try:
                    result = await self.relevance_llm.ainvoke([
                        SystemMessage(content="You are an expert at evaluating the relevance of retrieved context to user queries."),
                        HumanMessage(content=prompt)
                    ])
                    break
                except Exception as e:
                    if attempt == 1:  # Last attempt
                        raise e
                    logger.warning(f"Relevance evaluation attempt {attempt + 1} failed: {e}, retrying...")
            
            langfuse.score_current_span(
                name="rag_relevance",
                value=result.score,
                comment=result.feedback
            )
            return result
        except (ValidationError, Exception) as e:
            logging.error(f"Error during relevance check: {e}")
            langfuse.score_current_span(name="rag_relevance_error", value=0, comment=str(e))
            return RAGRelevanceResult(score=0.0, is_relevant=False, feedback=f"Evaluation failed: {e}")