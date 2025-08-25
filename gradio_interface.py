#!/usr/bin/env python3
"""
Gradio web interface for the Cybersecurity Multi-Agent Advisory System.
Provides a modern, user-friendly web interface for interacting with the cybersecurity team.
"""

import asyncio
import logging
import sys
import uuid
import concurrent.futures
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Generator
import datetime

import gradio as gr
from dotenv import load_dotenv

# --- Environment and Path Setup ---
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
dotenv_path = project_root / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)

# --- Logging Setup ---
from utils.logging import setup_logging
setup_logging(level=logging.INFO, log_to_console=True)
logger = logging.getLogger(__name__)

# --- Application Imports ---
from conversation.manager import ConversationManager
from workflow.graph import CybersecurityTeamGraph


class CybersecurityChatInterface:
    """
    Gradio-based chat interface for the cybersecurity advisory system.
    """
    
    def __init__(self):
        """Initialize the chat interface."""
        self.manager: Optional[ConversationManager] = None
        self.initialized = False
        
        # Consistent avatar for the cybersecurity team
        self.bot_avatar = "https://cdn-icons-png.flaticon.com/512/2092/2092063.png"
        
        # Session management for multi-chat support
        self.sessions: Dict[str, str] = {}  # Maps session_id to thread_id
    
    async def initialize_system(self) -> bool:
        """
        Initialize the cybersecurity advisory system.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("🚀 Initializing Enhanced Cybersecurity Advisory System for Gradio...")
            
            # Initialize workflow graph
            workflow = CybersecurityTeamGraph()
            
            # Create shared LLM client for conversation features
            from langchain_openai import ChatOpenAI
            from config.settings import settings
            llm_client = ChatOpenAI(
                model=settings.default_model,
                temperature=0.1,
                max_tokens=4000
            )
            
            # Initialize enhanced conversation manager with LLM support
            self.manager = ConversationManager(workflow=workflow, llm_client=llm_client)
            await self.manager.initialize()
            
            if self.manager.initialized:
                self.initialized = True
                logger.info("✅ Enhanced system initialized successfully for Gradio interface")
                return True
            else:
                logger.error("❌ System initialization failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ System initialization error: {e}")
            return False
    
    def get_thread_id(self, session_id: str) -> str:
        """Get or create a thread_id for a given session_id."""
        if session_id not in self.sessions:
            self.sessions[session_id] = f"gradio-session-{uuid.uuid4()}"
            logger.info(f"🔗 Started new conversation session: {self.sessions[session_id]}")
        return self.sessions[session_id]
    
    def clear_chat_session(self, session_id: str) -> Tuple[List[Tuple[str, str]], str]:
        """Clear the current chat session and start a new one."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        
        self.get_thread_id(session_id)  # Start a new session
        logger.info(f"🗑️ Cleared session {session_id}, starting new thread.")
        return [], ""

    async def process_message(
        self, 
        message: str, 
        history: List[List[str]], 
        session_id: str
    ) -> Generator[Tuple[List[List[str]], str], None, None]:
        """
        Process a user message with streaming status updates.
        
        Args:
            message: User's input message
            history: Conversation history as list of [user_msg, bot_msg] pairs
            session_id: The session identifier for multi-chat support
            
        Yields:
            Tuple of (updated_history, current_agent) for real-time updates
        """
        if not self.initialized or not self.manager:
            error_msg = "🚨 System not initialized. Please refresh the page and try again."
            yield history + [[message, error_msg]], "default"
            return
        
        try:
            # Get the thread_id for the current session
            thread_id = self.get_thread_id(session_id)
            
            # Add user message to history
            current_history = history + [[message, ""]]
            
            # Get actual response from the cybersecurity team
            logger.info(f"📝 Processing message in thread {thread_id[:8]}...")
            response = await self.manager.chat(message=message, thread_id=thread_id)
            
            # Final response
            current_history[-1][1] = response
            yield current_history
            
            logger.info(f"✅ Response generated successfully for thread {thread_id[:8]}")
            
        except Exception as e:
            error_msg = f"🚨 Sorry, I encountered an error processing your request: {str(e)}"
            logger.error(f"❌ Error processing message: {e}")
            final_history = history + [[message, error_msg]]
            yield final_history
    
    def get_example_queries(self) -> List[List[str]]:
        """
        Get example queries to help users get started.
        
        Returns:
            List of example queries as [input, None] pairs for Gradio examples
        """
        return [
            ["What are the latest DDoS prevention strategies?"],
            ["How should I respond to a suspected ransomware attack?"],
            ["What compliance requirements apply to healthcare data?"],
            ["Can you analyze this suspicious email attachment hash: d41d8cd98f00b204e9800998ecf8427e?"],
        ]
    
    def create_interface(self) -> gr.Blocks:
        """
        Create the Gradio interface.
        
        Returns:
            Configured Gradio Blocks interface
        """
        custom_css = """
        .gradio-container { 
            font-family: 'Inter', sans-serif; 
            background: #f8fafc;
        }
        .header { 
            background: #0f172a; 
            padding: 1.5rem; 
            color: white; 
            text-align: center; 
            border-bottom: 2px solid #3b82f6;
        }
        .header h1 { 
            font-size: 2rem; 
            font-weight: 700; 
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .header p { 
            font-size: 1rem; 
            opacity: 0.8; 
            margin-top: 0.5rem;
        }
        .main-layout { 
            display: flex; 
            gap: 1.5rem; 
            height: calc(100vh - 120px);
            padding: 1.5rem;
        }
        .left-panel { 
            flex: 1; 
            background: white; 
            border-radius: 8px; 
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            display: flex;
            flex-direction: column;
        }
        .right-panel { 
            flex: 3; 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .panel-header {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            align-items: center;
        }
        .panel-header svg { margin-right: 0.5rem; }
        .agent-list p { margin: 0.5rem 0; }
        .tips-box { background: #fef3c7; border-radius: 6px; padding: 1rem; }
        .chat-container { flex-grow: 1; overflow-y: auto; padding: 1rem; }
        .input-area { padding: 1rem; border-top: 1px solid #e2e8f0; }
        """
        
        with gr.Blocks(
            title="Cybersecurity Advisory System",
            theme=gr.themes.Soft(
                primary_hue="blue",
                secondary_hue="slate",
                neutral_hue="slate"
            ),
            css=custom_css
        ) as interface:
            
            session_id = gr.State(lambda: str(uuid.uuid4()))

            gr.HTML("""
            <div class="header">
                <h1>
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                    Cybersecurity Advisory System
                </h1>
                <p>AI-Powered Multi-Agent Security Consultation</p>
            </div>
            """)
            
            with gr.Row(elem_classes="main-layout"):
                with gr.Column(elem_classes="left-panel"):
                    gr.HTML("""
                    <h2 class="panel-header">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                        Available Security Specialists
                    </h2>
                    <div class="agent-list">
                        <p><strong>Sarah Chen</strong> - Incident Response</p>
                        <p><strong>Alex Rodriguez</strong> - Prevention & Architecture</p>
                        <p><strong>Dr. Kim Park</strong> - Threat Intelligence</p>
                        <p><strong>Maria Santos</strong> - Compliance</p>
                    </div>
                    <div style="flex-grow: 1;"></div>
                    <div class="tips-box">
                        <h3 class="panel-header" style="border: none; margin-bottom: 0.5rem;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
                            Quick Tips
                        </h3>
                        <ul>
                            <li>Ask about security incidents</li>
                            <li>Get compliance guidance</li>
                            <li>Analyze threats & hashes</li>
                            <li>Discuss prevention strategies</li>
                        </ul>
                    </div>
                    """)
                
                with gr.Column(elem_classes="right-panel"):
                    chatbot = gr.Chatbot(
                        label="Security Advisory Chat",
                        show_label=False,
                        container=False,
                        elem_classes="chat-container",
                        avatar_images=(
                            "https://api.dicebear.com/7.x/avataaars/svg?seed=User&backgroundColor=64748b",
                            self.bot_avatar
                        )
                    )
                    
                    with gr.Row(elem_classes="input-area"):
                        with gr.Column(scale=10):
                            msg = gr.Textbox(
                                label="Ask your cybersecurity question",
                                placeholder="Type your security question here and press Enter...",
                                lines=1,
                                show_label=False,
                                container=False
                            )
                        
                        with gr.Column(scale=1, min_width=100):
                            submit_btn = gr.Button("Ask Team", variant="primary")

            with gr.Row(style={"padding": "0 1.5rem"}):
                gr.Examples(
                    examples=self.get_example_queries(),
                    inputs=msg,
                    label="Example Questions"
                )
                clear_btn = gr.Button("🗑️ Clear Chat")

            async def handle_submit(message: str, history: List[List[str]], session_id_val: str):
                """Handle message submission with streaming."""
                if not message.strip():
                    return history, message
                
                async for updated_history in self.process_message(message, history, session_id_val):
                    yield updated_history, ""

            submit_btn.click(
                handle_submit,
                inputs=[msg, chatbot, session_id],
                outputs=[chatbot, msg],
                show_progress=True
            )
            
            msg.submit(
                handle_submit,
                inputs=[msg, chatbot, session_id],
                outputs=[chatbot, msg],
                show_progress=True
            )
            
            clear_btn.click(
                self.clear_chat_session,
                inputs=[session_id],
                outputs=[chatbot, msg],
                show_progress=True
            )
        
        return interface
    
    def launch(
        self, 
        host: str = "127.0.0.1", 
        port: int = 7860, 
        share: bool = False,
        debug: bool = False
    ) -> None:
        """
        Launch the Gradio interface.
        
        Args:
            host: Host to bind to
            port: Port to serve on
            share: Whether to create public link
            debug: Enable debug mode
        """
        # Initialize system first
        logger.info("🌐 Starting Gradio interface...")
        
        # Run initialization in async context
        async def init_and_launch():
            success = await self.initialize_system()
            if not success:
                logger.error("❌ Failed to initialize system. Cannot launch interface.")
                return
            
            # Create and launch interface
            interface = self.create_interface()
            
            logger.info(f"🚀 Launching interface on http://{host}:{port}")
            interface.launch(
                server_name=host,
                server_port=port,
                share=share,
                debug=debug,
                show_api=False,
                quiet=False,
                inbrowser=True  # Auto-open browser
            )
        
        # Run the async initialization and launch
        try:
            asyncio.run(init_and_launch())
        except KeyboardInterrupt:
            logger.info("👋 Gradio interface stopped by user")
        except Exception as e:
            logger.error(f"❌ Error launching interface: {e}")


def main():
    """Main entry point for the Gradio interface."""
    interface = CybersecurityChatInterface()
    interface.launch(
        host="127.0.0.1",
        port=7860,
        share=False,  # Set to True to create public link
        debug=False
    )


if __name__ == "__main__":
    main()
