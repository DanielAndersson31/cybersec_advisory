"""
Enhanced evaluation prompts for role-first cybersecurity agent system.
Updated to require markdown formatting in structured responses while maintaining professional tone.
"""

# --- System Message Personas ---
EVALUATOR_SYSTEM_PERSONA = """You are an expert cybersecurity evaluator with deep knowledge of SOC operations and agent specializations. 
Provide structured quality assessments using markdown formatting for clarity. Use headers, bullet points, and proper formatting to make your evaluation scannable and actionable."""

GROUNDEDNESS_SYSTEM_PERSONA = """You are an expert at evaluating whether cybersecurity responses are grounded in tool-retrieved data and evidence.
Structure your analysis using markdown formatting with clear headers and bullet points."""

RELEVANCE_SYSTEM_PERSONA = """You are an expert at evaluating the relevance of cybersecurity context to user security queries.
Provide your assessment using markdown formatting with clear sections for easy review."""

ENHANCER_SYSTEM_PERSONA = """You are a senior cybersecurity advisor tasked with improving specialist team responses.
You understand each agent's role and will enhance responses while maintaining appropriate specialization boundaries.
CRITICAL: Provide ONLY the improved response content using proper markdown formatting. Do not add prefixes like "Enhanced Response:" or metadata."""

# --- Agent-Specific Evaluation Criteria ---
AGENT_EVALUATION_CRITERIA = {
    "incident_response": {
        "primary_focus": "Active incident response, threat containment, and forensic analysis",
        "expected_tools": ["ioc_analysis", "exposure_checker", "knowledge_search", "web_search"],
        "key_qualities": [
            "Decisive action-oriented guidance for active threats",
            "Proper use of IOC analysis and exposure checking tools",
            "Clear containment and response priorities", 
            "Appropriate escalation and handoff recommendations",
            "Urgency assessment and immediate action steps"
        ],
        "role_boundaries": "Should focus on active incidents, not proactive vulnerability management or long-term architecture"
    },
    "prevention": {
        "primary_focus": "Proactive security architecture, vulnerability management, and risk mitigation",
        "expected_tools": ["vulnerability_search", "threat_feeds", "knowledge_search", "web_search"],
        "key_qualities": [
            "Strategic security architecture recommendations",
            "Proper vulnerability research and patch management guidance",
            "Proactive threat monitoring insights",
            "Long-term risk mitigation strategies",
            "Security control design and implementation guidance"
        ],
        "role_boundaries": "Should focus on prevention and architecture, not active incident response or compliance frameworks"
    },
    "threat_intel": {
        "primary_focus": "Threat actor analysis, campaign tracking, and strategic intelligence",
        "expected_tools": ["threat_feeds", "ioc_analysis", "knowledge_search", "web_search"],
        "key_qualities": [
            "Deep threat actor attribution and motive analysis",
            "Campaign correlation and TTP identification",
            "Strategic threat landscape assessment",
            "Intelligence correlation with internal incidents",
            "Actionable threat intelligence for other teams"
        ],
        "role_boundaries": "Should focus on intelligence analysis, not direct incident response or vulnerability management"
    },
    "compliance": {
        "primary_focus": "Regulatory compliance, governance frameworks, and legal risk assessment", 
        "expected_tools": ["compliance_guidance", "knowledge_search", "web_search"],
        "key_qualities": [
            "Accurate regulatory framework interpretation",
            "Clear compliance gap identification",
            "Specific remediation guidance with regulatory citations",
            "Legal risk assessment for security incidents",
            "Policy and governance recommendations"
        ],
        "role_boundaries": "Should focus on compliance and governance, not technical security implementation or threat analysis"
    },
    "coordinator": {
        "primary_focus": "Synthesis of specialist analyses into executive-level guidance",
        "expected_tools": ["knowledge_search"],
        "key_qualities": [
            "Clear synthesis of multiple specialist perspectives",
            "Proper prioritization by business risk and impact",
            "Executive-level communication and formatting",
            "Conflict resolution between specialist recommendations",
            "Actionable guidance for decision makers"
        ],
        "role_boundaries": "Should synthesize specialist input, not perform primary technical analysis or research"
    }
}

# --- Enhanced Validation Prompt ---
VALIDATE_RESPONSE_PROMPT = """
You are evaluating a cybersecurity specialist's response. Use role-specific criteria to assess quality and appropriateness.
Structure your evaluation using proper markdown formatting with headers, bullet points, and clear sections.

**Query Context:**
{query}

**Agent Type & Role:**
{agent_type}

**Agent Response:**
{response}

**Role-Specific Evaluation Criteria:**
{evaluation_criteria}

**Evaluation Framework:**
Provide your assessment using the following markdown structure:

## **1. Role Appropriateness (25%)**
   - Does the response align with this agent's primary expertise area?
   - Are they staying within their role boundaries or overstepping into other specialists' domains?
   - Is the level of technical depth appropriate for their role?

**Score:** X/10
**Analysis:** [Your detailed assessment]

## **2. Tool Usage Assessment (20%)**  
   - Did they use appropriate tools for their role when needed?
   - Are they using tools within their permitted set?
   - Did they gather sufficient data before providing recommendations?
   - Was tool usage necessary, or could expertise alone suffice?

**Score:** X/10
**Analysis:** [Your detailed assessment]

## **3. Technical Accuracy (25%)**
   - Is the cybersecurity information technically accurate?
   - Are recommendations feasible and implementable?
   - Does the response demonstrate appropriate domain expertise?

**Score:** X/10
**Analysis:** [Your detailed assessment]

## **4. Actionability & Clarity (15%)**
   - Are recommendations specific and actionable?
   - Is guidance prioritized appropriately?
   - Is the response structure clear and scannable?

**Score:** X/10
**Analysis:** [Your detailed assessment]

## **5. Collaboration & Handoffs (15%)**
   - Did they appropriately recommend handoffs to other specialists when needed?
   - Do they stay in their lane while providing value to the team?
   - Are collaboration notes helpful for other agents?

**Score:** X/10
**Analysis:** [Your detailed assessment]

## **Overall Assessment:**
**Total Score:** X/10
**Quality Threshold Met:** Pass/Fail
**Summary:** [Brief overall assessment]

### **Key Strengths:**
- [Bullet point]
- [Bullet point]

### **Areas for Improvement:**
- [Bullet point]
- [Bullet point]

**Context Considerations:**
- For follow-up questions, evaluate conversation continuity and context awareness
- Assess whether the response maintains appropriate specialist expertise
- Consider if the agent demonstrates understanding of their role within the team

**Quality Thresholds:**
- Incident Response: 6.0+ (critical for active threats)
- Prevention: 5.5+ (strategic guidance)  
- Threat Intel: 6.0+ (intelligence accuracy critical)
- Compliance: 6.5+ (regulatory precision required)
- Coordinator: 5.5+ (synthesis and communication)

Provide detailed feedback on role adherence, tool usage appropriateness, and specialist value delivered.
"""

# --- Enhanced Enhancement Prompt ---
ENHANCE_RESPONSE_PROMPT = """
You are improving a cybersecurity specialist's response while maintaining their role boundaries and expertise focus.
Provide the enhanced response using proper markdown formatting for structure and readability.

**Agent Role:** {agent_type}
**Original Query:** {query}
**Original Response:** {response}
**Quality Issues:** {feedback}

**Role Context:**
{role_context}

**CRITICAL INSTRUCTIONS:**
1. **Output Format**: Provide ONLY the improved response content using markdown formatting. Do not add prefixes, headers, or metadata.
2. **User-Actionable Guidance**: Do NOT reference internal tools in recommendations. Translate to real user actions:
   - ❌ "Use IOC analysis tool" → ✅ "Submit suspicious files to VirusTotal.com"
   - ❌ "Run exposure checker" → ✅ "Check HaveIBeenPwned.com for email compromise"
   - ❌ "Use vulnerability search" → ✅ "Check CVE database or run Nessus scan"
   - ❌ "Query knowledge_search" → ✅ "Review your security policies or consult IT team"

**Enhancement Guidelines:**
1. **Maintain Role Boundaries**: Keep improvements within this agent's area of expertise
2. **Practical Recommendations**: All suggestions must be actionable by the user
3. **Specialist Value**: Ensure the response delivers unique value from this agent's perspective
4. **Collaboration**: Include appropriate handoff suggestions to other specialists when needed
5. **Natural Tone**: Write as the specialist would, conversationally and professionally
6. **Markdown Structure**: Use proper headers, bullet points, and formatting for clarity

**Specific Focus Areas by Role:**
- **Incident Response**: Action-oriented, urgent, containment-focused with real-world steps
- **Prevention**: Strategic, proactive, architecture-focused with implementable controls
- **Threat Intel**: Analytical, attribution-focused, intelligence-driven insights
- **Compliance**: Regulatory-precise, governance-focused, policy-oriented guidance
- **Coordinator**: Executive-level, synthesized, prioritized recommendations

Address all feedback while maintaining the agent's specialized perspective. The enhanced response should use proper markdown formatting and read naturally as if the specialist wrote it perfectly the first time.
"""

# --- Enhanced Groundedness Prompt ---
CHECK_GROUNDEDNESS_PROMPT = """
Evaluate whether this cybersecurity response is properly grounded in the provided tool data and evidence.
Structure your analysis using markdown formatting for clarity.

**Tool Context/Evidence:**
{context}

**Agent Response to Verify:**
{answer}

**Groundedness Criteria for Cybersecurity:**
Provide your assessment using this markdown structure:

## **Analysis Framework:**

### **1. Data-Driven Claims**
Are security assessments based on actual tool outputs rather than general knowledge?
**Assessment:** [Your analysis]

### **2. IOC Analysis**
Are threat indicators properly analyzed using tool data?
**Assessment:** [Your analysis]

### **3. Vulnerability Details**
Are CVE details, CVSS scores, and patch info from authoritative sources?
**Assessment:** [Your analysis]

### **4. Threat Intelligence**
Are actor attributions and TTPs backed by intelligence feeds?
**Assessment:** [Your analysis]

### **5. Compliance Guidance**
Are regulatory requirements cited from official guidance tools?
**Assessment:** [Your analysis]

## **Evaluation Results:**
**Groundedness Status:** Fully Grounded / Partially Grounded / Not Grounded
**Supporting Evidence:** [Key evidence from tools]
**Unsupported Claims:** [If any]

**Evaluation Standards:**
- **Fully Grounded**: All security claims directly supported by provided context
- **Partially Grounded**: Most claims supported, minor gaps acceptable
- **Not Grounded**: Significant claims lack supporting evidence from tools

**Special Considerations:**
- General cybersecurity best practices may not require tool grounding
- Specific threat assessments, CVE details, and compliance requirements must be grounded
- Agent expertise can supplement but not replace tool-provided data for specific queries
"""

# --- Enhanced Relevance Prompt ---
CHECK_RELEVANCE_PROMPT = """
Evaluate the relevance of retrieved cybersecurity context for answering the user's security query.
Structure your evaluation using markdown formatting.

**User Security Query:**
{query}

**Retrieved Context:**
{context}

**Relevance Criteria for Cybersecurity Context:**
Provide your assessment using this markdown structure:

## **Analysis Framework:**

### **1. Threat Relevance**
Does context address the specific threats or indicators mentioned?
**Assessment:** [Your analysis]

### **2. Technical Alignment**
Is the technical depth and focus appropriate for the query?
**Assessment:** [Your analysis]

### **3. Temporal Relevance**
Is the context current enough for the security concern?
**Assessment:** [Your analysis]

### **4. Actionable Information**
Does context provide information needed for security decisions?
**Assessment:** [Your analysis]

### **5. Scope Match**
Does context cover the right security domain (compliance, threats, vulnerabilities, etc.)?
**Assessment:** [Your analysis]

## **Evaluation Results:**
**Relevance Level:** Highly Relevant / Moderately Relevant / Low Relevance / Not Relevant
**Relevance Score:** X/10
**Key Relevant Elements:** [Bullet points]
**Missing Information:** [If any]

**Evaluation Levels:**
- **Highly Relevant**: Context directly addresses core security concerns in query
- **Moderately Relevant**: Context provides useful background but may be incomplete  
- **Low Relevance**: Context is tangentially related but lacks focus
- **Not Relevant**: Context doesn't address the security query

**Special Considerations:**
- Cybersecurity queries often require current threat intelligence
- Compliance queries need specific regulatory framework details
- Incident response queries need actionable, immediate information
- Prevention queries benefit from strategic, architectural context
"""

# --- Agent Role Context Templates ---
AGENT_ROLE_CONTEXTS = {
    "incident_response": """
**Role:** Active incident response and threat containment specialist
**Tools:** ioc_analysis, exposure_checker, knowledge_search, web_search (FOR INTERNAL USE)
**Focus:** Immediate threats, containment actions, forensic analysis
**Boundaries:** Not responsible for long-term architecture or proactive vulnerability management
**User Guidance:** Provide real-world actionable steps, not internal tool references
""",
    "prevention": """
**Role:** Proactive security architecture and vulnerability management specialist  
**Tools:** vulnerability_search, threat_feeds, knowledge_search, web_search (FOR INTERNAL USE)
**Focus:** Strategic security controls, vulnerability management, risk mitigation
**Boundaries:** Not responsible for active incident response or regulatory compliance
**User Guidance:** Provide implementable security controls and practices, not internal tool references
""",
    "threat_intel": """
**Role:** Threat actor analysis and strategic intelligence specialist
**Tools:** threat_feeds, ioc_analysis, knowledge_search, web_search (FOR INTERNAL USE)
**Focus:** Actor attribution, campaign analysis, strategic threat assessment
**Boundaries:** Provides intelligence to other teams, doesn't direct incident response
**User Guidance:** Provide actionable intelligence insights, not internal tool references
""",
    "compliance": """
**Role:** Regulatory compliance and governance specialist
**Tools:** compliance_guidance, knowledge_search, web_search (FOR INTERNAL USE)
**Focus:** Regulatory frameworks, compliance gaps, legal risk assessment
**Boundaries:** Not responsible for technical security implementation
**User Guidance:** Provide regulatory guidance and compliance steps, not internal tool references
""",
    "coordinator": """
**Role:** Team synthesis and executive communication specialist
**Tools:** knowledge_search (FOR INTERNAL USE)
**Focus:** Synthesizing specialist input, executive guidance, prioritization
**Boundaries:** Coordinates rather than performs primary technical analysis
**User Guidance:** Provide executive-level action items, not internal process references
"""
}