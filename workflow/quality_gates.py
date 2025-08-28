import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe, get_client
from pydantic import ValidationError

from config.langfuse_settings import langfuse_config
from workflow.schemas import QualityGateResult, RAGRelevanceResult, RAGGroundednessResult
from config.evaluation_prompts import (
    EVALUATOR_SYSTEM_PERSONA,
    GROUNDEDNESS_SYSTEM_PERSONA,
    RELEVANCE_SYSTEM_PERSONA,
    ENHANCER_SYSTEM_PERSONA,
    VALIDATE_RESPONSE_PROMPT,
    ENHANCE_RESPONSE_PROMPT,
    CHECK_GROUNDEDNESS_PROMPT,
    CHECK_RELEVANCE_PROMPT,
    AGENT_ROLE_CONTEXTS,
)

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
        
        # These runnables now handle parsing and retries internally
        self.quality_llm = self.evaluator_llm.with_structured_output(QualityGateResult)
        self.groundedness_llm = self.evaluator_llm.with_structured_output(RAGGroundednessResult)
        self.relevance_llm = self.evaluator_llm.with_structured_output(RAGRelevanceResult)


    @observe()
    async def validate_response(
        self, query: str, response: str, agent_type: str, context_info: dict = None, fail_open: bool = True
    ) -> QualityGateResult:
        """Validates an agent's response using a detailed, LLM-based evaluation."""
        langfuse = get_client()
        
        # Log the exact input being sent to the quality gate for debugging
        logger.info(f"--- Validating Response for Quality ---\nQuery: {query}\nResponse: {response}\nAgent Type: {agent_type}\n------------------------------------")
        
        if not self.langfuse:
            return QualityGateResult(passed=True, overall_score=10.0, feedback="Langfuse offline.")

        evaluator_config = langfuse_config.create_agent_evaluator(agent_type)
        
        # Add context information to the evaluation if available
        context_context = ""
        if context_info:
            context_context = f"""
**Context Information:**
- Is follow-up question: {context_info.get('is_follow_up', False)}
- Context maintained: {context_info.get('context_maintained', True)}
- Previous context: {context_info.get('previous_context', 'N/A')}

"""
        
        evaluation_prompt = VALIDATE_RESPONSE_PROMPT.format(
            query=query,
            response=response,
            agent_type=agent_type,
            evaluation_criteria=evaluator_config['prompt']
        ) + context_context
        
        try:
            # The with_structured_output runnable handles parsing and retries.
            evaluation_message = [
                SystemMessage(content=EVALUATOR_SYSTEM_PERSONA),
                HumanMessage(content=evaluation_prompt)
            ]
            result = await self.quality_llm.ainvoke(evaluation_message)

            # Log the evaluation results including scores
            logger.info(f"--- Quality Evaluation Results ---")
            logger.info(f"Agent Type: {agent_type}")
            logger.info(f"Overall Score: {result.overall_score:.2f}")
            logger.info(f"Passed: {result.passed}")
            logger.info(f"Threshold: {evaluator_config.get('threshold', 'N/A')}")
            
            # Log individual scores if available
            if result.scores:
                logger.info(f"Individual Scores:")
                for criterion, score in result.scores.items():
                    logger.info(f"  - {criterion}: {score:.1f}/10")
            else:
                logger.info(f"Individual Scores: Not available")
                
            logger.info(f"Feedback: {result.feedback}")
            logger.info(f"------------------------------------")

            langfuse.score_current_span(
                name=f"{agent_type}_quality_score",
                value=result.overall_score,
                comment=result.feedback
            )
            langfuse.score_current_span(name="quality_gate_succeeded", value=1)
            return result

        except Exception as e:
            logging.error(f"Error during quality validation for {agent_type}: {e}")
            langfuse.score_current_span(name="quality_gate_execution_error", value=1, comment=str(e))
            langfuse.score_current_span(name="quality_gate_succeeded", value=0)
            return QualityGateResult(
                passed=fail_open,
                overall_score=0.0,
                feedback=f"Quality evaluation could not be performed: {str(e)[:200]}"
            )

    @observe()
    async def enhance_response(self, query: str, response: str, feedback: str, agent_type: str) -> str:
        """Improves a response that failed the quality gate, based on specific feedback."""
        langfuse = get_client()
        
        # ---> FIX: Build the role_context required by the enhancement prompt <---
        role_context = AGENT_ROLE_CONTEXTS.get(agent_type, "No specific role context found.")

        enhancement_prompt = ENHANCE_RESPONSE_PROMPT.format(
            query=query,
            response=response,
            feedback=feedback,
            agent_type=agent_type,
            role_context=role_context
        )
        
        try:
            enhanced_response = await self.evaluator_llm.ainvoke([
                SystemMessage(content=ENHANCER_SYSTEM_PERSONA),
                HumanMessage(content=enhancement_prompt)
            ])
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
        prompt = CHECK_GROUNDEDNESS_PROMPT.format(context=full_context, answer=answer)
        
        try:
            message = [
                SystemMessage(content=GROUNDEDNESS_SYSTEM_PERSONA),
                HumanMessage(content=prompt)
            ]
            result = await self.groundedness_llm.ainvoke(message)
            
            langfuse.score_current_span(
                name="rag_groundedness",
                value=1 if result.grounded else 0,
                comment=result.feedback
            )
            return result
        except (ValidationError, Exception) as e:
            logging.error(f"Error during groundedness check: {e}")
            langfuse.score_current_span(name="rag_groundedness_error", value=1, comment=str(e))
            return RAGGroundednessResult(grounded=False, feedback=f"Evaluation failed: {e}")

    @observe()
    async def check_relevance(self, query: str, context_chunks: List[str]) -> RAGRelevanceResult:
        """Checks if the retrieved context chunks are relevant to the user's query (RAG)."""
        langfuse = get_client()
        
        full_context = "\\n---\\n".join(context_chunks)
        prompt = CHECK_RELEVANCE_PROMPT.format(context=full_context, query=query)
        
        try:
            message = [
                SystemMessage(content=RELEVANCE_SYSTEM_PERSONA),
                HumanMessage(content=prompt)
            ]
            result = await self.relevance_llm.ainvoke(message)
            
            langfuse.score_current_span(
                name="rag_relevance",
                value=result.score,
                comment=result.feedback
            )
            return result
        except (ValidationError, Exception) as e:
            logging.error(f"Error during relevance check: {e}")
            langfuse.score_current_span(name="rag_relevance_error", value=1, comment=str(e))
            return RAGRelevanceResult(score=0.0, is_relevant=False, feedback=f"Evaluation failed: {e}")