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
        """Define role-specific evaluation prompts and thresholds for each agent type"""
        
        return {
            "incident_response": {
                "name": "Incident Response Specialist Evaluator",
                "prompt": """Evaluate this incident response specialist's performance:

**Role Context**: Active incident response, threat containment, forensic analysis
**Expected Tools**: ioc_analysis, exposure_checker, knowledge_search, web_search  
**Core Responsibilities**: Immediate threats, containment actions, breach investigation

**Evaluation Criteria (0-10 each):**

1. **Role Appropriateness**: Does the response focus on active incident response rather than prevention/architecture?
2. **Tool Usage**: Are appropriate tools used (IOC analysis, exposure checking) when investigating threats?  
3. **Technical Accuracy**: Are incident response procedures and threat assessments technically sound?
4. **Action Orientation**: Are recommendations immediate, decisive, and focused on containment?
5. **Collaboration**: Are proper handoffs suggested (e.g., to Prevention for architecture, to Threat Intel for attribution)?

**Provide JSON response:**
{
    "scores": {
        "role_appropriateness": <number>,
        "tool_usage": <number>, 
        "technical_accuracy": <number>,
        "action_orientation": <number>,
        "collaboration": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= 6.0>,
    "feedback": "<specific improvement suggestions focusing on incident response expertise>"
}""",
                "threshold": 6.0,
                "model": "gpt-4o",
                "weight": 1.0
            },
            
            "prevention": {
                "name": "Prevention Specialist Evaluator", 
                "prompt": """Evaluate this prevention specialist's performance:

**Role Context**: Proactive security architecture, vulnerability management, risk mitigation
**Expected Tools**: vulnerability_search, threat_feeds, knowledge_search, web_search
**Core Responsibilities**: Strategic security controls, vulnerability management, architectural guidance

**Evaluation Criteria (0-10 each):**

1. **Role Appropriateness**: Does the response focus on proactive prevention rather than incident response?
2. **Tool Usage**: Are vulnerability search and threat feeds used appropriately for strategic guidance?
3. **Technical Accuracy**: Are architectural recommendations and vulnerability assessments sound?
4. **Strategic Thinking**: Does the guidance consider long-term security posture and risk mitigation?
5. **Collaboration**: Are handoffs suggested when prevention identifies critical issues requiring incident response?

**Provide JSON response:**
{
    "scores": {
        "role_appropriateness": <number>,
        "tool_usage": <number>,
        "technical_accuracy": <number>, 
        "strategic_thinking": <number>,
        "collaboration": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= 5.5>,
    "feedback": "<specific improvement suggestions focusing on prevention expertise>"
}""",
                "threshold": 5.5,
                "model": "gpt-4o", 
                "weight": 0.9
            },
            
            "threat_intel": {
                "name": "Threat Intelligence Specialist Evaluator",
                "prompt": """Evaluate this threat intelligence specialist's performance:

**Role Context**: Threat actor analysis, campaign tracking, strategic intelligence  
**Expected Tools**: threat_feeds, ioc_analysis, knowledge_search, web_search
**Core Responsibilities**: Actor attribution, TTP analysis, strategic threat assessment

**Evaluation Criteria (0-10 each):**

1. **Role Appropriateness**: Does the response focus on intelligence analysis rather than direct incident response?
2. **Tool Usage**: Are threat feeds and IOC analysis used effectively for intelligence gathering?
3. **Technical Accuracy**: Are threat actor attributions and TTP analyses well-founded?
4. **Intelligence Quality**: Does the analysis provide valuable context, attribution, and actionable intelligence?
5. **Collaboration**: Does the intelligence support other teams (incident response, prevention) appropriately?

**Provide JSON response:**
{
    "scores": {
        "role_appropriateness": <number>,
        "tool_usage": <number>,
        "technical_accuracy": <number>,
        "intelligence_quality": <number>, 
        "collaboration": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= 6.0>,
    "feedback": "<specific improvement suggestions focusing on intelligence analysis expertise>"
}""",
                "threshold": 6.0,
                "model": "gpt-4o",
                "weight": 1.0
            },
            
            "compliance": {
                "name": "Compliance Specialist Evaluator",
                "prompt": """Evaluate this compliance specialist's performance:

**Role Context**: Regulatory compliance, governance frameworks, legal risk assessment
**Expected Tools**: compliance_guidance, knowledge_search, web_search  
**Core Responsibilities**: Regulatory interpretation, compliance gaps, policy guidance

**Evaluation Criteria (0-10 each):**

1. **Role Appropriateness**: Does the response focus on compliance/governance rather than technical security?
2. **Tool Usage**: Is compliance guidance tool used for authoritative regulatory information?
3. **Technical Accuracy**: Are regulatory interpretations and compliance requirements accurate?
4. **Regulatory Expertise**: Does the guidance demonstrate deep understanding of applicable frameworks?
5. **Collaboration**: Are compliance requirements clearly communicated to technical teams?

**Provide JSON response:**
{
    "scores": {
        "role_appropriateness": <number>,
        "tool_usage": <number>,
        "technical_accuracy": <number>,
        "regulatory_expertise": <number>,
        "collaboration": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= 6.5>,
    "feedback": "<specific improvement suggestions focusing on compliance expertise>"
}""",
                "threshold": 6.5,  # Higher threshold for compliance precision
                "model": "gpt-4o",
                "weight": 1.1
            },
            
            "coordinator": {
                "name": "Team Coordinator Evaluator",
                "prompt": """Evaluate this team coordinator's performance:

**Role Context**: Team synthesis, executive communication, specialist coordination
**Expected Tools**: knowledge_search (coordination only, not primary research)
**Core Responsibilities**: Synthesizing specialist input, prioritization, executive guidance

**Evaluation Criteria (0-10 each):**

1. **Role Appropriateness**: Does the response focus on synthesis/coordination rather than primary technical analysis?
2. **Tool Usage**: Is the coordinator staying within bounds (knowledge search only) and not doing web research?
3. **Synthesis Quality**: Are multiple specialist perspectives integrated effectively?
4. **Executive Communication**: Is the guidance formatted appropriately for decision makers?
5. **Prioritization**: Are recommendations properly prioritized by risk, impact, and feasibility?

**Provide JSON response:**
{
    "scores": {
        "role_appropriateness": <number>,
        "tool_usage": <number>,
        "synthesis_quality": <number>,
        "executive_communication": <number>,
        "prioritization": <number>
    },
    "overall": <average of all scores>,
    "passed": <true if overall >= 5.5>,
    "feedback": "<specific improvement suggestions focusing on coordination and synthesis>"
}""",
                "threshold": 5.5,
                "model": "gpt-4o", 
                "weight": 0.8
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
        """Get quality thresholds for all agent types (aligned with agent_config.py)"""
        return {
            "incident_response": 6.0,
            "prevention": 5.5, 
            "threat_intel": 6.0,
            "compliance": 6.5,
            "coordinator": 5.5
        }
    
    def log_evaluation(self, agent_type: str, score: float, 
                      feedback: str, metadata: Optional[Dict] = None):
        """Log evaluation results to Langfuse"""
        try:
            threshold = self.get_quality_thresholds().get(agent_type, 6.0)
            
            # Create comprehensive metadata
            eval_metadata = {
                "agent_type": agent_type,
                "timestamp": self._get_timestamp(),
                "threshold": threshold,
                "passed": score >= threshold,
                "role_specific_evaluation": True,
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
            
            # Log role-specific metrics
            self.client.score(
                name=f"{agent_type}_role_adherence",
                value="WITHIN_ROLE" if eval_metadata["passed"] else "ROLE_BOUNDARY_ISSUE", 
                data_type="CATEGORICAL",
                metadata=eval_metadata
            )
            
        except Exception as e:
            print(f"Failed to log evaluation to Langfuse: {e}")
    
    def log_tool_usage_evaluation(self, agent_type: str, tools_used: list, 
                                 appropriate_usage: bool, feedback: str):
        """Log tool usage evaluation specifically"""
        try:
            expected_tools = {
                "incident_response": ["ioc_analysis", "exposure_checker", "knowledge_search", "web_search"],
                "prevention": ["vulnerability_search", "threat_feeds", "knowledge_search", "web_search"], 
                "threat_intel": ["threat_feeds", "ioc_analysis", "knowledge_search", "web_search"],
                "compliance": ["compliance_guidance", "knowledge_search", "web_search"],
                "coordinator": ["knowledge_search"]
            }
            
            self.client.score(
                name=f"{agent_type}_tool_usage",
                value="APPROPRIATE" if appropriate_usage else "INAPPROPRIATE",
                data_type="CATEGORICAL",
                comment=feedback,
                metadata={
                    "agent_type": agent_type,
                    "tools_used": tools_used,
                    "expected_tools": expected_tools.get(agent_type, []),
                    "appropriate_usage": appropriate_usage,
                    "timestamp": self._get_timestamp()
                }
            )
        except Exception as e:
            print(f"Failed to log tool usage evaluation: {e}")
    
    def log_collaboration_evaluation(self, agent_type: str, handoffs_suggested: list,
                                   appropriate_collaboration: bool, feedback: str):
        """Log collaboration and handoff evaluation"""
        try:
            self.client.score(
                name=f"{agent_type}_collaboration", 
                value="GOOD_COLLABORATION" if appropriate_collaboration else "POOR_COLLABORATION",
                data_type="CATEGORICAL",
                comment=feedback,
                metadata={
                    "agent_type": agent_type,
                    "handoffs_suggested": handoffs_suggested,
                    "appropriate_collaboration": appropriate_collaboration,
                    "timestamp": self._get_timestamp()
                }
            )
        except Exception as e:
            print(f"Failed to log collaboration evaluation: {e}")
    
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
                    "enhancement_type": "role_focused_improvement",
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
        role_boundary_issues = []
        tool_usage_issues = []
        
        for agent_type, eval_data in evaluations.items():
            score = eval_data.get("overall_score", 0)
            total_score += score
            
            if eval_data.get("passed", False):
                passed_count += 1
            else:
                failed_agents.append(agent_type)
                
            # Check for specific issues
            if eval_data.get("scores", {}).get("role_appropriateness", 10) < 6:
                role_boundary_issues.append(agent_type)
            if eval_data.get("scores", {}).get("tool_usage", 10) < 6:
                tool_usage_issues.append(agent_type)
        
        return {
            "average_score": total_score / len(evaluations),
            "passed_count": passed_count,
            "failed_count": len(evaluations) - passed_count,
            "failed_agents": failed_agents,
            "role_boundary_issues": role_boundary_issues,
            "tool_usage_issues": tool_usage_issues,
            "all_passed": len(failed_agents) == 0,
            "evaluation_count": len(evaluations),
            "system_health": "GOOD" if len(failed_agents) == 0 else "NEEDS_ATTENTION"
        }


# Initialize global instance for use across the application
try:
    langfuse_config = LangfuseConfig()
    print("Langfuse configuration initialized successfully with role-specific evaluators")
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
            "threshold": langfuse_config.get_quality_thresholds().get(agent_type, 6.0) if langfuse_config else 6.0,
            "agent_type": agent_type,
            "offline_mode": True
        }