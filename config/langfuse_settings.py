from langfuse import Langfuse
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from config.settings import settings  # Import your settings


class LangfuseConfig:
    """Centralized Langfuse configuration for observability and evaluation"""
    
    def __init__(self):
        # Use settings from your settings.py file
        self.public_key = settings.get_secret("langfuse_public_key")
        self.secret_key = settings.get_secret("langfuse_secret_key")
        self.host = settings.langfuse_host
        
        # Validate that we have the required keys
        if not all([self.public_key, self.secret_key]):
            raise ValueError("Langfuse API keys not found in settings")
        
        # Initialize the Langfuse client
        self.client = Langfuse(
            public_key=self.public_key,
            secret_key=self.secret_key,
            host=self.host
        )
        
        # Track initialization time
        self.initialized_at = datetime.now(timezone.utc)
        print(f"Langfuse client initialized at {self.initialized_at}")
    
    def get_evaluator_prompts(self) -> Dict[str, Dict[str, Any]]:
        """Define evaluation prompts and thresholds for each agent type"""
        
        return {
            "incident_response": {
                "name": "Incident Response Quality Evaluator",
                "prompt": """Evaluate this incident response for:
1. Technical accuracy (0-10): Are the technical details correct and appropriate for the cybersecurity context?
2. Actionability (0-10): Are the recommendations clear, specific, and immediately actionable?
3. Completeness (0-10): Does the response address the main aspects of the query, including follow-up considerations?
4. Context awareness (0-10): Does it recognize if this is a follow-up question and maintain conversation continuity?
5. Urgency assessment (0-10): Does it appropriately assess the severity and urgency of the incident?

Provide a JSON response with this exact format:
{
    "scores": {
        "accuracy": <number>,
        "actionability": <number>,
        "completeness": <number>,
        "context_awareness": <number>,
        "urgency_assessment": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= threshold>,
    "feedback": "<specific improvement suggestions>"
}""",
                "threshold": 6.0,
                "model": "gpt-4o",
                "weight": 1.0  # Weight for overall scoring
            },
            
            "prevention": {
                "name": "Prevention Strategy Evaluator",
                "prompt": """Evaluate this prevention guidance for:
1. Technical accuracy (0-10): Are the technical details correct and appropriate for cybersecurity prevention?
2. Actionability (0-10): Are the recommendations clear, specific, and implementable?
3. Completeness (0-10): Does the response address the main aspects of the query, including follow-up considerations?
4. Context awareness (0-10): Does it recognize if this is a follow-up question and maintain conversation continuity?
5. Strategic thinking (0-10): Does it consider long-term prevention strategies and risk mitigation?

Provide a JSON response with this exact format:
{
    "scores": {
        "accuracy": <number>,
        "actionability": <number>,
        "completeness": <number>,
        "context_awareness": <number>,
        "strategic_thinking": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= threshold>,
    "feedback": "<specific improvement suggestions>"
}""",
                "threshold": 5.5,
                "model": "gpt-4o",
                "weight": 0.9
            },
            
            "threat_intel": {
                "name": "Threat Intelligence Quality Evaluator",
                "prompt": """Evaluate this threat intelligence analysis for:
1. Technical accuracy (0-10): Are the technical details correct and appropriate for threat intelligence?
2. Actionability (0-10): Are the recommendations clear, specific, and actionable for defenders?
3. Completeness (0-10): Does the response address the main aspects of the query, including follow-up considerations?
4. Context awareness (0-10): Does it recognize if this is a follow-up question and maintain conversation continuity?
5. Intelligence quality (0-10): Does it provide valuable threat context, indicators, and attribution insights?

Provide a JSON response with this exact format:
{
    "scores": {
        "accuracy": <number>,
        "actionability": <number>,
        "completeness": <number>,
        "context_awareness": <number>,
        "intelligence_quality": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= threshold>,
    "feedback": "<specific improvement suggestions>"
}""",
                "threshold": 6.0,
                "model": "gpt-4o",
                "weight": 1.0
            },
            
            "compliance": {
                "name": "Compliance Guidance Quality Evaluator",
                "prompt": """Evaluate this compliance guidance for:
1. Technical accuracy (0-10): Are the technical details correct and appropriate for regulatory compliance?
2. Actionability (0-10): Are the recommendations clear, specific, and implementable for compliance?
3. Completeness (0-10): Does the response address the main aspects of the query, including follow-up considerations?
4. Context awareness (0-10): Does it recognize if this is a follow-up question and maintain conversation continuity?
5. Regulatory expertise (0-10): Does it demonstrate proper understanding of compliance frameworks and requirements?

Provide a JSON response with this exact format:
{
    "scores": {
        "accuracy": <number>,
        "actionability": <number>,
        "completeness": <number>,
        "context_awareness": <number>,
        "regulatory_expertise": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= threshold>,
    "feedback": "<specific improvement suggestions>"
}""",
                "threshold": 6.5,  # Higher threshold for compliance due to regulatory importance
                "model": "gpt-4o",
                "weight": 1.1  # Slightly higher weight for compliance
            }
        }
    
    def create_agent_evaluator(self, agent_type: str) -> Dict[str, Any]:
        """Create evaluator configuration for a specific agent type"""
        
        evaluator_prompts = self.get_evaluator_prompts()
        
        # Return the specific evaluator or default to incident response
        evaluator = evaluator_prompts.get(
            agent_type, 
            evaluator_prompts["incident_response"]
        ).copy()  # Create a copy to avoid modifying the original
        
        # Add runtime configuration
        evaluator["timestamp"] = self._get_timestamp()
        evaluator["session_id"] = self._generate_session_id()
        evaluator["agent_type"] = agent_type
        
        return evaluator
    
    def get_quality_thresholds(self) -> Dict[str, float]:
        """Get quality thresholds for all agent types"""
        evaluators = self.get_evaluator_prompts()
        return {
            agent_type: config["threshold"]
            for agent_type, config in evaluators.items()
        }
    
    def log_evaluation(self, agent_type: str, score: float, 
                      feedback: str, metadata: Optional[Dict] = None):
        """Log evaluation results to Langfuse"""
        try:
            # Create comprehensive metadata
            eval_metadata = {
                "agent_type": agent_type,
                "timestamp": self._get_timestamp(),
                "threshold": self.get_quality_thresholds().get(agent_type, 7.0),
                "passed": score >= self.get_quality_thresholds().get(agent_type, 7.0),
                **(metadata or {})
            }
            
            # Log to Langfuse
            self.client.score(
                name=f"{agent_type}_quality",
                value=score,
                data_type="NUMERIC",
                comment=feedback,
                metadata=eval_metadata
            )
            
            # Also log pass/fail as categorical
            self.client.score(
                name=f"{agent_type}_quality_status",
                value="PASS" if eval_metadata["passed"] else "FAIL",
                data_type="CATEGORICAL",
                metadata=eval_metadata
            )
            
        except Exception as e:
            print(f"Failed to log evaluation to Langfuse: {e}")
    
    def log_enhancement(self, agent_type: str, original_score: float, 
                       enhanced_score: float, enhancement_reason: str):
        """Log response enhancement events"""
        try:
            self.client.score(
                name=f"{agent_type}_enhancement",
                value=enhanced_score - original_score,
                data_type="NUMERIC",
                comment=f"Enhanced from {original_score} to {enhanced_score}. Reason: {enhancement_reason}",
                metadata={
                    "original_score": original_score,
                    "enhanced_score": enhanced_score,
                    "improvement": enhanced_score - original_score,
                    "agent_type": agent_type,
                    "timestamp": self._get_timestamp()
                }
            )
        except Exception as e:
            print(f"Failed to log enhancement to Langfuse: {e}")
    
    def create_trace(self, name: str, metadata: Optional[Dict] = None) -> Any:
        """Create a new Langfuse trace for tracking"""
        try:
            return self.client.trace(
                name=name,
                metadata=metadata or {},
                timestamp=self._get_timestamp()
            )
        except Exception as e:
            print(f"Failed to create Langfuse trace: {e}")
            return None
    
    def flush(self):
        """Flush any pending Langfuse events"""
        try:
            self.client.flush()
        except Exception as e:
            print(f"Failed to flush Langfuse client: {e}")
    
    # Helper methods
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.now(timezone.utc).isoformat() + "Z"
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID for tracking"""
        return str(uuid.uuid4())
    
    def get_evaluation_summary(self, evaluations: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate summary statistics from multiple evaluations"""
        if not evaluations:
            return {"error": "No evaluations provided"}
        
        total_score = 0
        passed_count = 0
        failed_agents = []
        
        for agent_type, eval_data in evaluations.items():
            score = eval_data.get("overall_score", 0)
            total_score += score
            
            if eval_data.get("passed", False):
                passed_count += 1
            else:
                failed_agents.append(agent_type)
        
        return {
            "average_score": total_score / len(evaluations),
            "passed_count": passed_count,
            "failed_count": len(evaluations) - passed_count,
            "failed_agents": failed_agents,
            "all_passed": len(failed_agents) == 0,
            "evaluation_count": len(evaluations)
        }


# Initialize global instance for use across the application
try:
    langfuse_config = LangfuseConfig()
    print("Langfuse configuration initialized successfully")
except Exception as e:
    print(f"Warning: Langfuse initialization failed: {e}")
    print("Running in offline mode - Langfuse observability disabled")
    langfuse_config = None


# Export helper function for safe access
def get_langfuse_client() -> Optional[Langfuse]:
    """Get Langfuse client instance safely"""
    return langfuse_config.client if langfuse_config else None


# Export configuration getter
def get_evaluator_config(agent_type: str) -> Dict[str, Any]:
    """Get evaluator configuration safely"""
    if langfuse_config:
        return langfuse_config.create_agent_evaluator(agent_type)
    else:
        # Return minimal config if Langfuse is not available
        return {
            "name": f"{agent_type} evaluator (offline)",
            "threshold": 7.0,
            "agent_type": agent_type,
            "offline_mode": True
        }