#!/usr/bin/env python3
"""
Command-line interface for the Cybersecurity Multi-Agent Advisory System.
"""
import asyncio
import logging
import sys
import uuid
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# --- Environment and Path Setup ---
# 1. Add project root to Python's import path.
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 2. Explicitly load the .env file BEFORE other imports.
dotenv_path = project_root / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
    # Optional: print success message for debugging
    # print(f"SUCCESS: Loaded environment variables from {dotenv_path}")
else:
    print(f"WARNING: .env file not found at {dotenv_path}.")


# --- Logging Setup ---
# Initialize logging before other imports
from utils.logging import setup_logging

# Set up logging with INFO level for production
setup_logging(level=logging.INFO, log_to_console=True)
logger = logging.getLogger(__name__)

# --- Application Imports ---
# Now that the environment is loaded, we can safely import application components.
from conversation.manager import ConversationManager
from workflow.graph import CybersecurityTeamGraph

console = Console()
cli_app = typer.Typer()

async def initialize_system():
    """
    Initializes all necessary components for the advisory system.
    """
    logger.info("🚀 Initializing Cybersecurity Advisory System...")
    console.print("[bold green]Initializing Cybersecurity Advisory System...[/bold green]")
    
    # 1. Initialize the workflow graph (which now handles its own clients)
    workflow = CybersecurityTeamGraph()
    
    # 2. Initialize the conversation manager
    manager = ConversationManager(workflow=workflow)
    await manager.initialize() # Async initialization
    
    logger.info("✅ System initialized successfully")
    console.print("[bold green]System initialized successfully.[/bold green]")
    return manager

@cli_app.command()
def chat(
    query: str = typer.Argument(None, help="The initial query to the cybersecurity team. If omitted, starts an interactive chat session."),
    thread_id: str = typer.Option(f"cli-thread-{uuid.uuid4()}", "--thread-id", "-t", help="The conversation thread ID."),
):
    """
    Start a chat session with the cybersecurity agent team.
    """
    async def run_conversation():
        manager = None
        try:
            manager = await initialize_system()
            if not manager or not manager.initialized:
                console.print("[bold red]System initialization failed. Exiting.[/bold red]")
                raise typer.Exit(code=1)

            # If an initial query was provided, handle it first.
            if query:
                console.print(Panel(f"[bold yellow]Query:[/bold yellow] {query}", title="User Input", border_style="yellow"))
                response = await manager.chat(message=query, thread_id=thread_id)
                console.print(Panel(response, title="Team Response", border_style="green"))

            # Enter interactive chat loop
            logger.info("💬 Starting interactive chat mode")
            console.print("[bold cyan]Entering interactive chat mode. Type 'exit', 'quit', or 'q' to end.[/bold cyan]")
            while True:
                user_input = console.input("[bold yellow]You: [/bold yellow]")
                
                if user_input.lower() in ["exit", "quit", "q"]:
                    logger.info("👋 User ended session")
                    console.print("[bold cyan]Ending session. Goodbye![/bold cyan]")
                    break

                logger.info(f"📝 Processing user query: '{user_input[:50]}...'")
                response = await manager.chat(message=user_input, thread_id=thread_id)
                console.print(Panel(response, title="Team Response", border_style="green"))

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Session interrupted. Goodbye![/bold cyan]")
        finally:
            if manager:
                await manager.cleanup()

    asyncio.run(run_conversation())

if __name__ == "__main__":
    cli_app()
