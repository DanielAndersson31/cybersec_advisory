#!/usr/bin/env python3
"""
Gradio web interface for the Cybersecurity Multi-Agent Advisory System.
Provides a modern, user-friendly web interface for interacting with the cybersecurity team.
"""

import asyncio
import logging
import sys
import uuid
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Generator

import gradio as gr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from config.settings import settings
from utils.logging import setup_logging
from conversation.manager import ConversationManager
from workflow.graph import CybersecurityTeamGraph

# --- Environment and Path Setup ---
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
dotenv_path = project_root / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)

# --- Logging Setup ---
setup_logging(level=logging.INFO, log_to_console=True)
logger = logging.getLogger(__name__)


class CybersecurityChatInterface:
    """
    Gradio-based chat interface for the cybersecurity advisory system.
    """
    
    def __init__(self):
        """Initialize the chat interface."""
        self.manager: Optional[ConversationManager] = None
        self.initialized = False
        self.bot_avatar = "https://cdn-icons-png.flaticon.com/512/2092/2092063.png"
        self.sessions: Dict[str, str] = {}
        
        # Chat management
        self.chats: Dict[str, List[Dict[str, str]]] = {}
        self.chat_counter = 0
        self.current_chat_id: Optional[str] = None
        self._create_new_chat(is_init=True)  # Create the first chat on initialization

    def _get_chat_list_and_current_name(self):
        """Helper to get sorted chat names and the current chat's name."""
        chat_list_keys = sorted(self.chats.keys(), key=lambda x: int(x.split('_')[1]))
        chat_list_names = [f"Chat {k.split('_')[1]}" for k in chat_list_keys]
        current_chat_name = f"Chat {self.current_chat_id.split('_')[1]}" if self.current_chat_id else ""
        return chat_list_names, current_chat_name

    def _create_new_chat(self, is_init: bool = False):
        """Creates a new chat session and sets it as the current one."""
        self.chat_counter += 1
        chat_id = f"chat_{self.chat_counter}"
        
        initial_message = "Hello! How can I assist you with your cybersecurity needs today?"
        self.chats[chat_id] = [] if is_init else [{"role": "assistant", "content": initial_message}]
        
        self.current_chat_id = chat_id
        self.sessions[chat_id] = f"gradio-session-{uuid.uuid4()}"
        logger.info(f"🆕 Created new chat: {chat_id}")
        
        chat_list_names, current_chat_name = self._get_chat_list_and_current_name()
        return self.chats[self.current_chat_id], chat_list_names, current_chat_name, self.current_chat_id

    def _delete_current_chat(self):
        """Deletes the currently active chat."""
        if len(self.chats) <= 1:
            logger.warning("⚠️ Attempted to delete the last remaining chat.")
            return self.chats[self.current_chat_id], *self._get_chat_list_and_current_name(), self.current_chat_id

        chat_id_to_delete = self.current_chat_id
        if chat_id_to_delete in self.chats:
            del self.chats[chat_id_to_delete]
        if chat_id_to_delete in self.sessions:
            del self.sessions[chat_id_to_delete]
        
        logger.info(f"🗑️ Deleted chat: {chat_id_to_delete}")

        # Switch to the first available chat
        self.current_chat_id = sorted(self.chats.keys(), key=lambda x: int(x.split('_')[1]))[0]
        
        return self.chats[self.current_chat_id], *self._get_chat_list_and_current_name(), self.current_chat_id

    def _switch_chat(self, chat_name: str):
        """Switches the active chat based on the selected name from the UI."""
        if not chat_name or not isinstance(chat_name, str):
            return self.chats[self.current_chat_id], self.current_chat_id

        try:
            chat_num = chat_name.split(' ')[1]
            chat_id = f"chat_{chat_num}"
            
            if chat_id in self.chats:
                self.current_chat_id = chat_id
                logger.info(f"🔄 Switched to chat: {self.current_chat_id}")
            else:
                logger.warning(f"⚠️ Tried to switch to non-existent chat: {chat_id}")

        except (IndexError, ValueError) as e:
            logger.error(f"❌ Invalid chat name format '{chat_name}': {e}")

        return self.chats[self.current_chat_id], self.current_chat_id

    async def handle_submit(self, message: str, history: List[Dict[str, str]], session_id: str):
        """Handles message submission, streaming the response."""
        if not message.strip():
            yield history, ""
            return
        
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": ""})

        if self.current_chat_id:
            self.chats[self.current_chat_id] = history
        yield history, ""

        async for updated_history in self.process_message(message, history, session_id):
            if self.current_chat_id:
                self.chats[self.current_chat_id] = updated_history
            yield updated_history, ""
    
    async def initialize_system(self) -> bool:
        """Initializes the backend systems for the chat interface."""
        try:
            logger.info("🚀 Initializing Enhanced Cybersecurity Advisory System for Gradio...")
            workflow = CybersecurityTeamGraph()
            llm_client = ChatOpenAI(model=settings.default_model, temperature=0.1, max_tokens=4000)
            
            self.manager = ConversationManager(workflow=workflow, llm_client=llm_client)
            await self.manager.initialize()
            
            if self.manager.initialized:
                self.initialized = True
                logger.info("✅ Enhanced system initialized successfully for Gradio interface")
                return True
            
            logger.error("❌ System initialization failed")
            return False
                
        except Exception as e:
            logger.error(f"❌ System initialization error: {e}")
            return False
    
    def get_thread_id(self, session_id: str) -> str:
        """Gets or creates a thread_id for a given session_id."""
        if session_id not in self.sessions:
            self.sessions[session_id] = f"gradio-session-{uuid.uuid4()}"
            logger.info(f"🔗 Started new conversation session: {self.sessions[session_id]}")
        return self.sessions[session_id]
    
    def clear_chat_session(self) -> Tuple[List, str]:
        """Clears the history of the current chat session."""
        if self.current_chat_id:
            self.chats[self.current_chat_id] = []
            logger.info(f"🗑️ Cleared history for session {self.current_chat_id}.")
        return [], ""

    async def process_message(self, message: str, history: List[Dict[str, str]], session_id: str
    ) -> Generator[List[Dict[str, str]], None, None]:
        """Processes a user message and yields the updated history."""
        if not self.initialized or not self.manager:
            history[-1]["content"] = "🚨 System not initialized. Please refresh."
            yield history
            return
        
        try:
            thread_id = self.get_thread_id(session_id)
            logger.info(f"📝 Processing message in thread {thread_id[:8]}...")
            response = await self.manager.chat(message=message, thread_id=thread_id)
            history[-1]["content"] = response
            yield history
            logger.info(f"✅ Response generated successfully for thread {thread_id[:8]}")
            
        except Exception as e:
            error_msg = f"🚨 Sorry, an error occurred: {str(e)}"
            logger.error(f"❌ Error processing message: {e}")
            history[-1]["content"] = error_msg
            yield history
    
    def get_example_queries(self) -> List[str]:
        """Returns a list of example queries for the user."""
        return [
            "What are the latest DDoS prevention strategies?",
            "How should I respond to a suspected ransomware attack?",
            "What compliance requirements apply to healthcare data?",
            "Can you analyze this suspicious email attachment hash: d41d8cd98f00b204e9800998ecf8427e?",
        ]
    
    def create_interface(self) -> gr.Blocks:
        """Creates and configures the Gradio interface."""
        custom_css = """
        :root {
            --primary-color: #3b82f6; --secondary-color: #1e293b; --background-color: #f1f5f9;
            --card-background: #ffffff; --text-color: #334155; --header-text-color: #ffffff;
            --border-color: #e2e8f0;
        }
        body { margin: 0; }
        .gradio-container { font-family: 'Inter', sans-serif; background: var(--background-color); height: 100vh; overflow: hidden; }
        .header { background: var(--secondary-color); padding: 1rem 1.5rem; color: var(--header-text-color); text-align: center; border-bottom: 3px solid var(--primary-color); }
        .header h1 { font-size: 1.6rem; font-weight: 600; margin: 0; display: flex; align-items: center; justify-content: center; color: var(--header-text-color); }
        .header p { font-size: 0.9rem; opacity: 0.8; margin-top: 0.3rem; color: var(--header-text-color); }
        .cybersecurity-badge { background: var(--primary-color); color: white; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600; margin-left: 1rem; text-transform: uppercase; letter-spacing: 0.5px; }
        .main-layout { display: grid; grid-template-columns: 280px 1fr; gap: 1.5rem; height: calc(100vh - 80px); padding: 1.5rem; }
        .left-panel { background: var(--card-background); border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.05); display: flex; flex-direction: column; border: 1px solid var(--border-color); overflow-y: auto; }
        .panel-header { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border-color); display: flex; align-items: center; justify-content: space-between; color: var(--text-color); }
        .chat-list-header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 1rem; }
        .new-chat-btn { max-width: 40px; }
        #chat-list-radio .gr-form { background: transparent; border: none; box-shadow: none; gap: 0.5rem; }
        #chat-list-radio .gr-form .gr-radio-label { border: 1px solid var(--border-color); padding: 0.75rem; border-radius: 8px; cursor: pointer; }
        #chat-list-radio .gr-form .gr-radio-label:hover { background: #f1f5f9; }
        #chat-list-radio .gr-form input[type="radio"]:checked + .gr-radio-label { background: var(--primary-color); color: white; border-color: var(--primary-color); }
        .agent-item { display: flex; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #f1f5f9; }
        .agent-icon { width: 24px; height: 24px; margin-right: 0.75rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; color: white; }
        .agent-icon.incident { background: #ef4444; } .agent-icon.prevention { background: #10b981; } .agent-icon.threat { background: #f59e0b; } .agent-icon.compliance { background: #8b5cf6; }
        .right-panel { background: var(--card-background); border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--border-color); }
        .chat-container { flex-grow: 1; overflow-y: auto; padding: 1.5rem; }
        .input-area { padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); background: #f8fafc; }
        .examples-area { padding: 0 1.5rem 1rem 1.5rem; background: #f8fafc; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }
        """
        
        with gr.Blocks(title="Cybersecurity Advisory System", theme=gr.themes.Soft(primary_hue="blue"), css=custom_css) as interface:
            
            initial_chat_list, initial_chat_name = self._get_chat_list_and_current_name()
            current_chat_id = gr.State(self.current_chat_id)

            gr.HTML("""
            <div class="header">
                <h1>
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                    &nbsp;Cybersecurity Advisory System <span class="cybersecurity-badge">🛡️ Security</span>
                </h1>
                <p>AI-Powered Multi-Agent Security Consultation & Threat Analysis</p>
            </div>
            """)
            
            with gr.Row(elem_classes="main-layout"):
                with gr.Column(elem_classes="left-panel"):
                    with gr.Row(elem_classes="chat-list-header"):
                        gr.HTML("<span><b>Conversations</b></span>")
                        new_chat_btn = gr.Button("+ New", size="sm", variant="primary", elem_classes="new-chat-btn")
                    
                    chat_list = gr.Radio(
                        initial_chat_list, label="Chats", show_label=False, container=False, 
                        elem_id="chat-list-radio", value=initial_chat_name
                    )
                    
                    delete_chat_btn = gr.Button("🗑️ Delete Chat", size="sm", variant="secondary", visible=True)
                    gr.HTML("<hr style='border-top: 1px solid var(--border-color); margin: 1rem 0;'>")
                    
                    gr.HTML("""
                    <h2 class="panel-header">Available Specialists</h2>
                    <div class="agent-list">
                        <div class="agent-item"><div class="agent-icon incident">SC</div><div><strong>Sarah Chen</strong> - Incident Response</div></div>
                        <div class="agent-item"><div class="agent-icon prevention">AR</div><div><strong>Alex Rodriguez</strong> - Prevention & Architecture</div></div>
                        <div class="agent-item"><div class="agent-icon threat">KP</div><div><strong>Dr. Kim Park</strong> - Threat Intelligence</div></div>
                        <div class="agent-item"><div class="agent-icon compliance">MS</div><div><strong>Maria Santos</strong> - Compliance</div></div>
                    </div>
                    """)
                
                with gr.Column(elem_classes="right-panel"):
                    chatbot = gr.Chatbot(
                        [{"role": "assistant", "content": "Hello! How can I assist you with your cybersecurity needs today?"}],
                        label="Security Advisory Chat", show_label=False, container=False, elem_classes="chat-container",
                        avatar_images=("https://api.dicebear.com/7.x/avataaars/svg?seed=User&backgroundColor=64748b", self.bot_avatar),
                        type="messages"
                    )
                    
                    with gr.Row(elem_classes="input-area"):
                        msg = gr.Textbox(
                            label="Ask your cybersecurity question", placeholder="Type your security question here...", 
                            lines=1, show_label=False, container=False, scale=9
                        )
                        submit_btn = gr.Button("Ask Team", variant="primary", scale=1, min_width=120)
                        clear_btn = gr.Button("Clear", variant="secondary", scale=1, min_width=80)

                    gr.Examples(self.get_example_queries(), inputs=msg, label="Example Questions")

            # --- Event Listeners ---
            
            # Typing and submitting
            msg.submit(self.handle_submit, [msg, chatbot, current_chat_id], [chatbot, msg])
            submit_btn.click(self.handle_submit, [msg, chatbot, current_chat_id], [chatbot, msg])
            
            # Chat management
            def new_chat_handler():
                history, new_list, new_name, new_id = self._create_new_chat()
                return history, gr.update(choices=new_list, value=new_name), new_id

            def delete_chat_handler():
                history, new_list, new_name, new_id = self._delete_current_chat()
                return history, gr.update(choices=new_list, value=new_name), new_id
                
            def switch_chat_handler(chat_name: str):
                history, new_id = self._switch_chat(chat_name)
                return history, new_id

            new_chat_btn.click(new_chat_handler, outputs=[chatbot, chat_list, current_chat_id])
            delete_chat_btn.click(delete_chat_handler, outputs=[chatbot, chat_list, current_chat_id])
            chat_list.select(switch_chat_handler, inputs=chat_list, outputs=[chatbot, current_chat_id])
            clear_btn.click(self.clear_chat_session, outputs=[chatbot, msg])
        
        return interface
    
    def launch(self, host: str = "127.0.0.1", port: int = 7860, **kwargs):
        """Launches the Gradio interface after initializing the system."""
        async def init_and_launch():
            if await self.initialize_system():
                interface = self.create_interface()
                logger.info(f"🚀 Launching interface on http://{host}:{port}")
                interface.launch(server_name=host, server_port=port, **kwargs)
            else:
                logger.error("❌ Failed to initialize system. Aborting launch.")
        
        try:
            asyncio.run(init_and_launch())
        except Exception as e:
            logger.error(f"❌ An error occurred during launch: {e}")

def main():
    """Main entry point for the Gradio interface."""
    interface = CybersecurityChatInterface()
    interface.launch(share=False, debug=False, inbrowser=True)

if __name__ == "__main__":
    main()
