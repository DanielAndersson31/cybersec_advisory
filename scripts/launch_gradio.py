#!/usr/bin/env python3
"""
Launch script for the Gradio web interface of the Cybersecurity Advisory System.
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gradio_interface import CybersecurityChatInterface


def main():
    """Launch the Gradio interface with command-line options."""
    parser = argparse.ArgumentParser(
        description="Launch the Cybersecurity Advisory System Gradio Interface"
    )
    
    parser.add_argument(
        "--host", 
        default="127.0.0.1", 
        help="Host to bind to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=7860, 
        help="Port to serve on (default: 7860)"
    )
    
    parser.add_argument(
        "--share", 
        action="store_true", 
        help="Create a public Gradio link"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug mode"
    )
    
    args = parser.parse_args()
    
    print("🛡️  Cybersecurity Advisory System - Gradio Interface")
    print("=" * 60)
    print(f"Starting interface on http://{args.host}:{args.port}")
    
    if args.share:
        print("📡 Public sharing enabled - a public link will be created")
    
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Create and launch interface
    interface = CybersecurityChatInterface()
    interface.launch(
        host=args.host,
        port=args.port,
        share=args.share,
        debug=args.debug
    )


if __name__ == "__main__":
    main()
