#!/usr/bin/env python3
"""
Command-line interface for the Cybersecurity Multi-Agent Advisory System.
"""
import asyncio
import typer
from rich.console import Console
from rich.panel import Panel

# Correctly import all necessary components
from conversation.manager import ConversationManager
from workflow.graph import CybersecurityTeamGraph
from cybersec_mcp.cybersec_client import CybersecurityMCPClient
from openai import AsyncOpenAI
from config.settings import settings

console = Console()
cli_app = typer.Typer()

async def initialize_system():
    """
    Initializes all necessary components for the advisory system.
    """
    console.print("[bold green]Initializing Cybersecurity Advisory System...[/bold green]")
    
    # 1. Initialize clients
    llm_client = AsyncOpenAI(api_key=settings.get_secret("openai_api_key"))
    mcp_client = CybersecurityMCPClient()
    
    # 2. Initialize the workflow graph
    workflow = CybersecurityTeamGraph(llm=llm_client, mcp_client=mcp_client)
    
    # 3. Initialize the conversation manager
    manager = ConversationManager(workflow=workflow)
    await manager.initialize() # Async initialization
    
    console.print("[bold green]System initialized successfully.[/bold green]")
    return manager

@cli_app.command()
def chat(
    query: str = typer.Argument(..., help="The initial query to the cybersecurity team."),
    thread_id: str = typer.Option("default-cli-thread", "--thread-id", "-t", help="The conversation thread ID."),
):
    """
    Start a chat session with the cybersecurity agent team.
    """
    async def run_conversation():
        manager = await initialize_system()
        if not manager:
            console.print("[bold red]System initialization failed. Exiting.[/bold red]")
            raise typer.Exit(code=1)

        console.print(Panel(f"[bold yellow]Query:[/bold yellow] {query}", title="User Input", border_style="yellow"))

        response = await manager.chat(message=query, thread_id=thread_id)
        
        console.print(Panel(response, title="Team Response", border_style="green"))

    asyncio.run(run_conversation())

if __name__ == "__main__":
    cli_app()
