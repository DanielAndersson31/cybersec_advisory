# Agent and Tool Capability Test Prompts

This file contains a curated list of advanced prompts designed to test the full capabilities of each specialized agent and their respective tools.

### 1. Incident Response Agent (with `ioc_analysis` and `web_search`)

**Prompt:** "We've detected suspicious outbound traffic to the IP address 185.125.190.27 and our firewall logs show DNS requests for the domain 'dynamobilliards.com'. Can you analyze these indicators, tell me what threat this might be, and recommend immediate containment steps?"

**Purpose:** Tests the agent's ability to handle multiple indicators of compromise (IOCs), use the `ioc_analysis` tool for threat identification, and provide actionable incident response guidance.

### 2. Prevention Specialist (with `vulnerability_search`)

**Prompt:** "We are planning to deploy a new server running Apache Struts version 2.3.34. Can you perform a vulnerability assessment on this version, highlight any critical CVEs we should be aware of, and recommend a secure deployment strategy?"

**Purpose:** Tests the `vulnerability_search` tool for a specific software version and the agent's ability to provide proactive, preventative security advice.

### 3. Threat Analyst (with `threat_feeds` and `web_search`)

**Prompt:** "I need a threat intelligence briefing on the latest activities of the APT group 'Fancy Bear' (APT28). What are their recent tactics, techniques, and procedures (TTPs), and are there any new indicators of compromise we should be monitoring for?"

**Purpose:** Pushes the `threat_feeds` tool to gather intelligence on a specific threat actor and tests the agent's ability to synthesize this into a high-level briefing.

### 4. Compliance Advisor (with `compliance_guidance` and `knowledge_search`)

**Prompt:** "Our organization is a healthcare provider, and we are developing a new patient portal. What are the key HIPAA security rule requirements we must implement to protect patient data, and can you provide a checklist of technical controls we need to have in place?"

**Purpose:** Tests the `compliance_guidance` tool for a specific regulatory framework (HIPAA) and the agent's ability to provide detailed, actionable compliance advice.

### 5. Multi-Agent Collaboration (Incident + Threat + Compliance)

**Prompt:** "We've confirmed a Log4j vulnerability (CVE-2021-44228) has been exploited on one of our public-facing web servers, and we're seeing data exfiltration. We need a coordinated response plan that covers immediate incident containment, a full threat analysis of the attacker's potential access, and our legal obligations for notifying affected parties under GDPR."

**Purpose:** A complex scenario designed to trigger a multi-agent response, testing the coordinator's ability to synthesize a comprehensive plan from multiple expert perspectives.

### 6. General Assistant (with `web_search` for complex, real-time info)

**Prompt:** "What is the current global cybersecurity threat landscape according to the latest reports from the last three months? Summarize the top 3 emerging threats and provide links to the reports."

**Purpose:** Tests the `web_search` tool's ability to handle complex, time-sensitive queries that require synthesizing information from multiple sources.

### 7. Prevention & Threat Analysis (Cross-functional)

**Prompt:** "Based on recent threat intelligence, what are the most common attack vectors for ransomware in the financial services industry? Provide a prioritized list of preventative controls we should implement to mitigate these specific threats."

**Purpose:** Requires the system to first use threat intelligence tools to identify risks and then use prevention expertise to recommend specific controls, testing inter-agent knowledge.

### 8. Incident Response & Vulnerability (Cross-functional)

**Prompt:** "A user in our finance department reported a convincing phishing email that they clicked on. The email mentioned a recent vulnerability in Microsoft Office. Can you identify any critical Office vulnerabilities from the last month and provide a step-by-step guide for what our security team should do right now?"

**Purpose:** Combines a real-world incident with a need for specific vulnerability data, testing the system's ability to provide both immediate response actions and deeper technical context.

### 9. Knowledge Base & Compliance

**Prompt:** "Our internal policy requires multi-factor authentication for all critical systems. Where can I find the official documentation for this policy in our knowledge base, and can you summarize the key exceptions to this rule as outlined in the document?"

**Purpose:** Directly tests the `knowledge_search` tool and the system's ability to accurately retrieve and summarize information from internal documentation.

### 10. Web Search (Advanced - Disambiguation)

**Prompt:** "There's a lot of news about a new security threat called 'PonyFinal'. Is this a type of ransomware, a threat actor, or something else? Provide a brief summary of what it is and its primary method of attack."

**Purpose:** Tests the web search tool's ability to handle ambiguous or emerging threat names, requiring it to disambiguate the term and provide a concise, accurate summary.

### 11. Ambiguous & Challenging Prompts

This section includes short, unclear prompts designed to test the system's disambiguation, routing, and reasoning capabilities.

**Prompt:** "My computer is acting weird."

**Purpose:** A classic vague user statement. Tests the system's ability to ask clarifying questions and guide the user toward providing more specific information. The ideal response would be to engage in a dialogue to narrow down the problem (e.g., "Can you describe what you mean by 'weird'? Are you seeing slow performance, unexpected pop-ups, or something else?").

**Prompt:** "Is our firewall secure?"

**Purpose:** This question is broad and requires context. It should test the system's ability to recognize that it cannot give a simple "yes" or "no" answer. It should prompt the user for more information or suggest a course of action (e.g., "To assess your firewall's security, I would need to know more about its configuration and the policies it's enforcing. Could you provide more details, or would you like me to suggest a security assessment plan?").

**Prompt:** "How do I deal with a security alert?"

**Purpose:** This is a common but very general question. It should test the agent's ability to provide a structured, general framework for handling alerts while also emphasizing the need for specifics. A good response would outline the basic steps (identify, analyze, contain, eradicate, recover) and then ask for details about the specific alert.

**Prompt:** "Latest security news."

**Purpose:** This tests the system's ability to handle a very short, direct command. It should trigger a `web_search` and return a concise summary of the most recent cybersecurity headlines, demonstrating its ability to handle less conversational queries.
