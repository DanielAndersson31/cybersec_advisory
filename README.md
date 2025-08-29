# Cybersecurity Multi-Agent Advisory System

## Overview

The Cybersecurity Multi-Agent Advisory System is a sophisticated, AI-powered platform designed to provide expert-level cybersecurity guidance through a conversational interface. It leverages a team of specialized AI agents to deliver real-time, context-aware advice on a wide range of security topics, from incident response to compliance and threat analysis.

This system is built to serve as an intelligent assistant for cybersecurity professionals, automating complex information retrieval and providing actionable, expert-level recommendations.

## Core Features

- **Multi-Agent Architecture**: Queries are intelligently routed to a team of specialized AI agents, including an Incident Responder, Prevention Specialist, Threat Analyst, and Compliance Advisor, ensuring expert handling of every issue.
- **Intelligent Tool Use**: Agents are equipped with a suite of powerful tools, allowing them to perform real-time web searches, query vulnerability databases (CVEs), and search an internal knowledge base for policies and architectural documents.
- **Adaptive Web Search**: The system uses a two-stage web search that starts with a fast, "basic" search and automatically escalates to a more thorough, "advanced" search if the initial results are insufficient, balancing speed with comprehensiveness.
- **Context-Aware Conversation**: The system maintains conversational context, allowing for natural follow-up questions and a more intuitive user experience.
- **Quality Assurance**: A built-in quality gate evaluates the accuracy and relevance of all responses before they are delivered to the user, ensuring a high standard of reliability.

## System Architecture

The project is built on a modular architecture designed for scalability and maintainability:

- **Frontend**: A clean and intuitive user interface built with HTML, CSS, and JavaScript.
- **Workflow Engine**: A powerful orchestration layer that manages the flow of information between agents and tools using a state graph.
- **Specialized Agents**: Each agent is an expert in a specific domain of cybersecurity, with its own set of tools and a distinct persona.
- **Cybersecurity Toolkit**: A centralized set of tools that can be assigned to agents, including `web_search`, `vulnerability_search`, and `knowledge_search`.

## Getting Started

To get the system up and running, follow these steps:

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    ```
2.  **Install dependencies**:
    ```bash
    poetry install
    ```
3.  **Configure environment variables**:
    - Create a `.env` file and populate it with the necessary API keys and configuration settings.
4.  **Run the application**:
    ```bash
    python main.py
    ```

## Usage

To get the most out of the system, phrase your questions as if you were speaking to a team of human cybersecurity experts. Here are a few examples:

- **For the Incident Responder**: "We've detected suspicious outbound traffic to the IP 192.168.1.100. What are our immediate containment steps?"
- **For the Prevention Specialist**: "What are the most critical vulnerabilities for Apache Struts version 2.3.34?"
- **For the Knowledge Base**: "What is our company's policy on data encryption for remote employees?"
- **For Web Search**: "What are the latest tactics being used by the APT group Fancy Bear?"

## Recent Enhancements

We have recently completed a series of significant improvements to the web search functionality, ensuring it is fast, reliable, and consistent across all agents. These changes include:

- **Consistent result counts** (always 5)
- **Adaptive search depth** (basic, then advanced)
- **Improved result formatting** for better LLM comprehension

This project is under active development. We welcome your feedback and contributions!
