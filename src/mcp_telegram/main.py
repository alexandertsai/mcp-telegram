#!/usr/bin/env python3

import os
import sys
import logging
import json
import asyncio
import time
from telethon import TelegramClient
from telethon.sessions import StringSession, MemorySession
from telethon.errors import SessionPasswordNeededError
from mcp.server.fastmcp import FastMCP
from typing import Dict, List, Any, Optional
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Configure logging
log_dir = os.path.expanduser("~/telegram_mcp_logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "telegram_mcp.log")

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename=log_file,
    filemode='a'
)
logger = logging.getLogger(__name__)

# Add stderr handler for critical errors
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.CRITICAL)
formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s %(message)s')
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

# Create a global event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

class TelegramServer:
    def __init__(self, client):
        self.client = client
        self.app = FastMCP("telegram")
        self.register_tools()
    
    def register_tools(self):
        """Register Telegram-related tools with the MCP server"""
        
        @self.app.tool()
        def get_chats(page: int, page_size: int = 20) -> str:
            """
            Used when checking messages. Gets a paginated list of chats from Telegram. 
            
            Args:
                page: Page number (1-indexed).
                page_size: Number of chats per page.
            """
            try:
                # For page 1, start from the beginning
                if page == 1:
                    dialogs = loop.run_until_complete(
                        self.client.get_dialogs(limit=page_size)
                    )
                else:
                    # For subsequent pages, we need to get all previous dialogs first
                    # to determine the correct offset parameters
                    all_previous = loop.run_until_complete(
                        self.client.get_dialogs(limit=(page - 1) * page_size)
                    )
                    
                    # If we don't have enough results for previous pages
                    if len(all_previous) < (page - 1) * page_size:
                        return json.dumps([], indent=2)
                    
                    # Get the last dialog from the previous page to use as offset
                    last_dialog = all_previous[-1]
                    
                    # Use the date, ID and peer of the last message as offset
                    dialogs = loop.run_until_complete(
                        self.client.get_dialogs(
                            limit=page_size,
                            offset_date=last_dialog.date,
                            offset_id=last_dialog.message.id if last_dialog.message else 0,
                            offset_peer=last_dialog.entity
                        )
                    )
                
                result = []
                for dialog in dialogs:
                    chat = {
                        "id": dialog.id,
                        "name": dialog.name,
                        "unread_count": dialog.unread_count,
                        "type": str(dialog.entity.__class__.__name__)
                    }
                    result.append(chat)
                
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error fetching chats: {str(e)}")
                return json.dumps({"error": str(e)})
                
        @self.app.tool()
        def get_messages(chat_id: int, page: int, page_size: int = 20) -> str:
            """
            Get paginated messages from a specific chat from Telegram.
            
            Args:
                chat_id: The ID of the chat.
                page: Page number (1-indexed).
                page_size: Number of messages per page.
            """
            offset = (page - 1) * page_size
            limit = page_size
            
            try:
                # Use the global event loop consistently
                messages = loop.run_until_complete(
                    self.client.get_messages(chat_id, limit=limit, offset_id=0, offset_date=None, add_offset=offset)
                )
                
                result = []
                for message in messages:
                    msg = {
                        "id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.text,
                        "sender_id": message.sender_id,
                        "reply_to_msg_id": message.reply_to_msg_id
                    }
                    result.append(msg)
                
                return json.dumps(result, indent=2)
            except Exception as e:
                logger.error(f"Error fetching messages: {str(e)}")
                return json.dumps({"error": str(e)})
            
        @self.app.tool()
        def mark_messages_read(chat_id: int) -> str:
            """
            Mark all unread messages in a specific Telegram chat as read.
            
            Args:
                chat_id: The ID of the chat whose messages should be marked as read.
            """
            try:
                # Use the global event loop consistently
                # The read_history method marks messages as read
                result = loop.run_until_complete(
                    self.client.send_read_acknowledge(entity=chat_id)
                )
                return json.dumps({
                    "success": True, 
                    "message": f"Successfully marked messages as read in chat {chat_id}"
                })
            except Exception as e:
                logger.error(f"Error marking messages as read: {str(e)}")
                return json.dumps({"success": False, "error": str(e)})
                
        @self.app.tool()
        def send_message(chat_id: int, message: str, reply_to_msg_id: int = None) -> str:
            """
            Send a message to a specific chat in Telegram.
            
            Args:
                chat_id: The ID of the chat.
                message: The message content to send.
                reply_to_msg_id: Optional ID of a message to reply to. If provided, this message will be a reply to that specific message.
            """
            try:
                # Use the global event loop consistently
                result = loop.run_until_complete(
                    self.client.send_message(
                        entity=chat_id, 
                        message=message,
                        reply_to=reply_to_msg_id  # This parameter tells Telegram this is a reply to a specific message
                    )
                )
                return json.dumps({
                    "success": True, 
                    "message_id": result.id,
                    "is_reply": reply_to_msg_id is not None,
                    "replied_to_message_id": reply_to_msg_id
                })
            except Exception as e:
                logger.error(f"Error sending message: {str(e)}")
                return json.dumps({
                    "success": False, 
                    "error": str(e),
                    "is_reply": reply_to_msg_id is not None,
                    "replied_to_message_id": reply_to_msg_id
                })
        
        @self.app.tool()
        def get_conversation_context(chat_id: int, message_count: int = 20) -> str:
            """
            Get previous messages from a Telegram chat to analyze conversation context and style.
            
            This function retrieves recent messages from a specific chat to help
            Claude understand the conversational style and tone, allowing it to
            generate responses that match the existing conversation pattern.
            The function also reads a user-defined style guide from convostyle.txt
            to further refine the response style.
            
            Args:
                chat_id: The ID of the chat to analyze.
                message_count: Number of recent messages to retrieve (default: 20).
            """
            try:
                # Get messages from the chat
                messages = loop.run_until_complete(
                    self.client.get_messages(chat_id, limit=message_count)
                )
                
                # Process and organize the conversation
                conversation = []
                sender_info = {}
                
                # First pass: collect unique senders and their information
                for msg in messages:
                    if msg.sender_id and msg.sender_id not in sender_info:
                        try:
                            # Get sender information
                            entity = loop.run_until_complete(
                                self.client.get_entity(msg.sender_id)
                            )
                            sender_name = getattr(entity, 'first_name', '') or getattr(entity, 'title', '') or str(msg.sender_id)
                            sender_info[msg.sender_id] = {
                                'id': msg.sender_id,
                                'name': sender_name,
                                'is_self': msg.out
                            }
                        except Exception as e:
                            # If we can't get entity info, use minimal information
                            sender_info[msg.sender_id] = {
                                'id': msg.sender_id,
                                'name': f"User {msg.sender_id}",
                                'is_self': msg.out
                            }
                
                # Second pass: organize messages into conversation format
                # Start with newest messages first in the API response, so we reverse to get chronological order
                for msg in reversed(messages):
                    if not msg.text:  # Skip non-text messages
                        continue
                    
                    sender = sender_info.get(msg.sender_id, {'name': 'Unknown', 'is_self': False})
                    
                    conversation.append({
                        'timestamp': msg.date.isoformat(),
                        'sender_name': sender['name'],
                        'is_self': sender['is_self'],
                        'text': msg.text,
                        'message_id': msg.id
                    })
                
                # Read the user's conversation style guide
                style_guide = ""
                style_guide_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convostyle.txt")
                
                try:
                    with open(style_guide_path, 'r', encoding='utf-8') as file:
                        style_guide = file.read().strip()
                    logger.info(f"Successfully read style guide from {style_guide_path}")
                except Exception as e:
                    logger.warning(f"Could not read style guide file: {str(e)}")
                    style_guide = "Style guide file not available. Focus only on conversation history."
                
                # Add analysis information to help Claude
                result = {
                    'conversation': conversation,
                    'user_style_guide': style_guide,
                    'analysis_instructions': """
                        You're helping generate messages that match the user's texting style. 
                        To do this effectively:
                        
                        1. FIRST, carefully read the user's own description of their texting style in the 'user_style_guide' field.
                           This is the primary source of information about how they want to come across in messages.
                        
                        2. SECOND, analyze the conversation history to understand both:
                           - The overall conversation context (topic, relationship between participants)
                           - Specific examples of the user's actual writing style in practice, paying attention to:
                             * Tone (formal, casual, friendly, professional)
                             * Typical message length
                             * Use of emoji, slang, abbreviations, or special formatting
                             * Common greeting/closing patterns
                             * Sentence structure and vocabulary level
                        
                        3. SYNTHESIS: Blend the explicit style guide with observed patterns in their messages,
                           but when there's any conflict, the explicit style guide takes precedence.
                        
                        Generate a response that feels authentic to both how they say they write
                        and how they actually write, while being appropriate to the current conversation.
                    """
                }
                
                return json.dumps(result, indent=2, ensure_ascii=False)
                
            except Exception as e:
                logger.error(f"Error getting conversation context: {str(e)}")
                return json.dumps({
                    "error": str(e),
                    "message": "Failed to retrieve conversation context"
                })
    
    def run(self):
        """Run the MCP server"""
        self.app.run(transport='stdio')

def main():
    # Get Telegram API credentials
    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')
    phone = os.environ.get('TELEGRAM_PHONE')
    
    if not api_id or not api_hash or not phone:
        logger.critical("Please set TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_PHONE environment variables")
        sys.exit(1)
    
    # Session paths
    session_path = os.path.expanduser(f"~/.telegram_mcp_{phone}")
    session_string_file = f"{session_path}.string"
    session_string = None
    
    # Load session string if available
    if os.path.exists(session_string_file):
        try:
            with open(session_string_file, 'r') as f:
                session_string = f.read().strip()
            logger.info(f"Loaded session string from {session_string_file}")
        except Exception as e:
            logger.warning(f"Failed to load session string: {str(e)}")
    
    try:
        # Create a regular TelegramClient (not SyncTelegramClient)
        # and use it with our consistent event loop
        if session_string:
            client = TelegramClient(StringSession(session_string), api_id, api_hash, loop=loop)
        else:
            client = TelegramClient(MemorySession(), api_id, api_hash, loop=loop)
        
        # Connect using our loop
        loop.run_until_complete(client.connect())
        
        # Check authorization
        if not loop.run_until_complete(client.is_user_authorized()):
            logger.critical(f"Not authenticated. Please run the authentication script first.")
            logger.critical(f"Run: python telethon_auth.py")
            sys.exit(1)
        
        # Save session string if needed
        if not session_string:
            try:
                session_string = client.session.save()
                with open(session_string_file, 'w') as f:
                    f.write(session_string)
                logger.info(f"Saved session string to {session_string_file}")
            except Exception as e:
                logger.warning(f"Failed to save session string: {str(e)}")
        
        logger.info(f"Successfully connected to Telegram with authenticated session")
        
        # Create and run server
        server = TelegramServer(client)
        server.run()
        
    except Exception as e:
        logger.critical(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up
        if 'client' in locals():
            loop.run_until_complete(client.disconnect())

if __name__ == "__main__":
    main()