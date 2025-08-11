# tests/test_agents.py

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

# We are testing the agent classes, so we need to import them
from agents.incident_responder import IncidentResponderAgent
from agents.config import AgentRole

# This allows us to run async tests with pytest
pytestmark = pytest.mark.asyncio


@patch("agents.base_agent.get_agent_config")
@patch("agents.base_agent.get_agent_tools")
async def test_incident_agent_tool_call_workflow(
    mock_get_agent_tools, mock_get_agent_config
):
    """
    Tests the full tool-calling workflow for the IncidentResponseAgent.
    """
    # --- 1. SETUP ---
    # Mock the configuration files to return predictable data for our test
    mock_get_agent_config.return_value = {
        "name": "Sarah Chen (Test)",
        "role": AgentRole.INCIDENT_RESPONSE,
        "model": "test-model",
        "temperature": 0.1,
        "max_tokens": 1000,
    }
    # Mock the tools this agent is allowed to use
    mock_get_agent_tools.return_value = [
        {
            "name": "ioc_analysis_tool",
            "description": "Analyzes an IOC.",
            "parameters": {"type": "object", "properties": {"indicator": {"type": "string"}}},
        }
    ]

    # Mock the external clients
    mock_llm_client = AsyncMock()
    mock_mcp_client = AsyncMock()

    # --- 2. CONFIGURE MOCKS ---
    # This is the most important part: we define how the mocks will behave.
    
    # Configure the FIRST LLM response: Simulate the LLM deciding to call a tool.
    mock_first_llm_response = AsyncMock()
    mock_first_llm_response.choices = [
        AsyncMock(
            message=AsyncMock(
                tool_calls=[
                    AsyncMock(
                        id="call_123",
                        function=AsyncMock(
                            name="ioc_analysis_tool",
                            arguments='{"indicator": "198.51.100.10"}',
                        ),
                    )
                ],
                content=None # No text content, just a tool call
            )
        )
    ]
    
    # Configure the SECOND LLM response: Simulate the LLM giving a final answer
    # after receiving the tool's output.
    mock_second_llm_response = AsyncMock()
    mock_second_llm_response.choices = [
        AsyncMock(
            message=AsyncMock(
                tool_calls=None, # No more tool calls
                content="The IP 198.51.100.10 is a known C2 server. We must block it immediately.",
                # The model_dump() method is called in the agent, so our mock needs it.
                model_dump=lambda: {
                    "role": "assistant",
                    "content": "The IP 198.51.100.10 is a known C2 server. We must block it immediately."
                }
            )
        )
    ]

    # Assign the responses to the mock client's call sequence
    mock_llm_client.chat.completions.create.side_effect = [
        mock_first_llm_response,
        mock_second_llm_response,
    ]

    # Configure the mock tool client to return a predictable result
    mock_mcp_client.analyze_ioc.return_value = {
        "status": "malicious",
        "threat_actor": "Sand Serpent",
    }

    # --- 3. EXECUTION ---
    # Instantiate the agent with our mocked clients
    incident_agent = IncidentResponderAgent(
        llm_client=mock_llm_client, mcp_client=mock_mcp_client
    )

    # Define the user query and initial message history
    test_messages = [
        {"role": "user", "content": "We're seeing suspicious traffic from 198.51.100.10. What should we do?"}
    ]

    # Run the agent's respond method
    final_response = await incident_agent.respond(test_messages)

    # --- 4. ASSERTIONS ---
    # Verify that our mocks were called as expected.

    # Check that the tool client was called correctly
    mock_mcp_client.analyze_ioc.assert_called_once_with(indicator="198.51.100.10")

    # Check that the LLM was called twice (once for tool selection, once for synthesis)
    assert mock_llm_client.chat.completions.create.call_count == 2
    
    # Check that the final response content is what we configured in the second LLM call
    expected_content = "The IP 198.51.100.10 is a known C2 server. We must block it immediately."
    assert final_response["content"] == expected_content
    
    print("\n✅ Test passed successfully!")
    print(f"Final Agent Response: {final_response['content']}")


# To run this test:
# 1. Make sure you have pytest and pytest-asyncio installed:
#    pip install pytest pytest-asyncio
# 2. Save the code above as `tests/test_agents.py`.
# 3. Run pytest from your project's root directory:
#    pytest