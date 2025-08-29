# Cybersecurity Multi-Agent Advisory System

## Overview

The Cybersecurity Multi-Agent Advisory System is a production-ready, AI-powered platform that provides expert-level cybersecurity guidance through intelligent agent collaboration. Built with modern Python architecture and LangGraph orchestration, it delivers real-time, context-aware security advice across incident response, threat analysis, prevention strategies, and compliance requirements.

This system serves as an intelligent force multiplier for cybersecurity professionals, automating complex analysis tasks and providing actionable, expert-level recommendations through natural conversation.

## 🚀 Key Features

### **Multi-Agent Intelligence**

- **Specialized Expert Agents**: Sarah Chen (Incident Response), Dr. Kim Park (Threat Intelligence), Alex Rodriguez (Prevention), Maria Santos (Compliance)
- **Intelligent Routing**: Automatic query classification and expert assignment
- **Dynamic Coordination**: Seamless single-agent responses or multi-agent collaboration
- **Context Continuity**: Maintains conversation history and specialist context across interactions

### **Production-Grade Architecture**

- **LangGraph Orchestration**: State-based workflow management with checkpointing
- **Dependency Injection**: Clean architecture with proper separation of concerns
- **Quality Gates**: LLM-as-a-Judge response validation and enhancement
- **Comprehensive Tooling**: 8+ specialized cybersecurity tools with async execution

### **Advanced Capabilities**

- **RAG-Powered Knowledge Base**: Semantic search across cybersecurity documentation using Qdrant vector store
- **Real-Time Intelligence**: Live threat feeds, vulnerability databases, and web search integration
- **Compliance Expertise**: Built-in guidance for GDPR, HIPAA, PCI-DSS, SOX and other frameworks
- **IOC Analysis**: Automated indicator analysis using VirusTotal with configurable thresholds

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend Interface                           │
│              (Web UI + CLI + FastAPI)                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                 Workflow Engine                                 │
│           (LangGraph + Query Router)                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                 Agent Factory                                   │
│         (Dynamic Agent Creation + DI)                          │
└─────────────┬───────────────────────────────┬───────────────────┘
              │                               │
    ┌─────────▼─────────┐         ┌──────────▼──────────┐
    │ Specialist Agents │         │ Cybersecurity       │
    │                   │         │ Toolkit             │
    │ • Incident Response│◄────────┤                     │
    │ • Threat Intel     │         │ • IOC Analysis      │
    │ • Prevention       │         │ • Vulnerability DB  │
    │ • Compliance       │         │ • Knowledge Search  │
    │ • Coordinator      │         │ • Web Search        │
    └───────────────────┘         │ • Threat Feeds      │
                                  │ • Attack Surface    │
                                  │ • Exposure Checker  │
                                  │ • Compliance Guide  │
                                  └─────────────────────┘
```

### **Core Components**

#### **Workflow Layer** (`workflow/`)

- **Router**: Intelligent query classification and agent assignment
- **Nodes**: Orchestrated workflow steps (analysis, consultation, synthesis)
- **Quality Gates**: Response validation and enhancement systems
- **State Management**: LangGraph-based conversation state with checkpointing

#### **Agent Layer** (`agents/`)

- **Base Agent**: Shared tool execution and response structuring
- **Factory Pattern**: Dynamic agent creation with centralized prompts
- **Specialist Personas**: Domain-specific expertise and tool access

#### **Tools Layer** (`cybersec_mcp/tools/`)

- **Production Tools**: 8 specialized cybersecurity analysis tools
- **Async Architecture**: Non-blocking tool execution with proper error handling
- **Pydantic Schemas**: Type-safe request/response models

#### **Knowledge Layer** (`knowledge/`)

- **Vector Store**: Qdrant-powered semantic search with BGE embeddings
- **Dynamic Ingestion**: Multi-format document processing (PDF, MD, TXT, DOCX)
- **Domain Organization**: Structured knowledge domains (incident_response, compliance, etc.)

## 📋 Prerequisites

- **Python 3.11+** with full type hints support
- **Poetry** for dependency management
- **API Keys**: OpenAI, VirusTotal, Tavily, ZoomEye (optional)
- **Vector Database**: Qdrant (local or cloud)

## 🛠️ Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd cybersec_advisory
poetry install
```

### 2. Environment Configuration

Create `.env` file with required API keys:

```env
# Required
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key

# Optional but recommended
VIRUSTOTAL_API_KEY=your_virustotal_api_key
ZOOMEYE_API_KEY=your_zoomeye_api_key
ALIENVAULT_API_KEY=your_alienvault_api_key

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key  # Optional for local

# Langfuse (Optional - for observability)
LANGFUSE_SECRET_KEY=your_langfuse_secret
LANGFUSE_PUBLIC_KEY=your_langfuse_public
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. Knowledge Base Setup

```bash
# Initialize the knowledge base with your documents
python scripts/run_knowledge_base_setup.py
```

### 4. Launch the System

**Web Interface:**

```bash
python main.py
# Access at http://127.0.0.1:8000
```

**Command Line:**

```bash
python cybersec_advisory_cli.py chat "Analyze this suspicious IP: 192.168.1.100"
```

## 💬 Usage Examples

### **Incident Response**

```
"We detected unusual PowerShell activity on workstation WS-001.
The process was spawned by outlook.exe and is making network connections
to 185.220.100.240. What's our immediate response?"
```

### **Threat Intelligence**

```
"Can you analyze the domain evil-site.com and check if it's associated
with any known threat actors? Also check recent IOCs from this infrastructure."
```

### **Prevention & Compliance**

```
"We're implementing a new cloud architecture on AWS. What are the key
security controls for GDPR compliance, and what vulnerabilities should
we scan for in our container images?"
```

### **Multi-Agent Consultation**

```
"Our customer database was potentially accessed by an unauthorized user.
We store EU citizen data and payment information. What's our complete
response plan including legal obligations?"
```

## 🔧 Configuration

### **Agent Customization** (`config/agent_config.py`)

- Tool permissions per agent role
- Response quality thresholds
- Specialist personas and capabilities

### **Compliance Frameworks** (`config/compliance_frameworks.py`)

- Regulatory requirement mappings
- Breach notification timelines
- Framework-specific guidance

### **Tool Configuration**

- Configurable threat detection thresholds
- API rate limiting and retry logic
- Custom knowledge domains

## 🧪 Testing

```bash
# Run comprehensive test suite
poetry run pytest

# Test specific components
poetry run pytest tests/test_agents/
poetry run pytest tests/test_tools/
```

## 📊 Monitoring & Observability

The system includes comprehensive observability through:

- **Langfuse Integration**: Request tracing and performance monitoring
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Quality Metrics**: Response validation scores and enhancement tracking
- **Tool Performance**: Execution time and success rate monitoring

## 🏗️ Architecture Highlights

### **Design Patterns**

- **Factory Pattern**: Dynamic agent creation with dependency injection
- **Strategy Pattern**: Pluggable routing and tool selection strategies
- **Observer Pattern**: Quality gate validation and enhancement
- **Repository Pattern**: Clean knowledge base abstraction

### **Quality Assurance**

- **Type Safety**: Comprehensive Pydantic models throughout
- **Error Handling**: Graceful degradation with structured error responses
- **Retry Logic**: Resilient external API integration
- **Response Validation**: LLM-as-a-Judge quality assessment

### **Performance Optimizations**

- **Async Architecture**: Non-blocking I/O for all external calls
- **Efficient Embeddings**: Local BGE model with optimized vector search
- **Smart Caching**: Vector embeddings and API response caching
- **Batch Processing**: Concurrent tool execution and IOC analysis

## 🤝 Contributing

We welcome contributions! Please see our contribution guidelines for:

- Code style standards (Black, Ruff, type hints)
- Testing requirements and patterns
- Documentation standards
- Security considerations for cybersecurity tools

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🚀 Roadmap

- [ ] **Enhanced Threat Intelligence**: Additional threat feed integrations
- [ ] **Advanced Analytics**: Trend analysis and predictive capabilities
- [ ] **Custom Tool Framework**: Plugin architecture for organization-specific tools
- [ ] **Multi-Language Support**: Internationalization for global compliance
- [ ] **Mobile Interface**: Responsive design for mobile incident response

---

**Built with ❤️ for the cybersecurity community**

_This system represents the cutting edge of AI-powered cybersecurity assistance, combining the expertise of specialized agents with real-time intelligence capabilities._
