"""
Centralized prompts for the QualityGateSystem to separate configuration from logic.
This makes it easier to version, test, and update prompts without code changes.
"""

# --- System Message Personas ---

EVALUATOR_SYSTEM_PERSONA = "You are an expert cybersecurity evaluator. Provide structured quality assessments."
GROUNDEDNESS_SYSTEM_PERSONA = "You are an expert at evaluating whether responses are grounded in provided context."
RELEVANCE_SYSTEM_PERSONA = "You are an expert at evaluating the relevance of retrieved context to user queries."
ENHANCER_SYSTEM_PERSONA = """You are an expert cybersecurity advisor tasked with improving a team member's work. 
You will be given a response and feedback, and you must rewrite the response to address the feedback.
Provide only the improved, final response."""


# --- Prompt Templates ---

VALIDATE_RESPONSE_PROMPT = """
You are an expert cybersecurity evaluator. Your task is to evaluate the following response with strict objectivity.

**Original Query:**
{query}

**Agent Type:**
{agent_type}

**Agent Response to Evaluate:**
{response}

---
**Evaluation Criteria:**
{evaluation_criteria}

---
**Instructions:**
Be thorough and critical. Specifically, assess the response for technical accuracy, completeness, actionability, and appropriate tone.
Return your evaluation in the required structured format.
"""

ENHANCE_RESPONSE_PROMPT = """
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
"""

CHECK_GROUNDEDNESS_PROMPT = """
You are a meticulous fact-checker. Your task is to determine if the following statement is fully supported by the provided context.

**Context:**
{context}

---
**Statement to Verify:**
{answer}

---
**Instructions:**
Compare the statement against the context. The statement must be directly and explicitly supported by the context.
Provide your assessment in the required structured format.
"""

CHECK_RELEVANCE_PROMPT = """
You are a relevance assessor. Your task is to determine if the provided context is relevant for answering the user's query.

**User Query:**
{query}

---
**Context to Evaluate:**
{context}

---
**Instructions:**
Evaluate how relevant the context is for forming a comprehensive answer to the user's query.
Provide your assessment in the required structured format.
"""
