#!/usr/bin/env python3

import os
import sys
import json
from telethon import TelegramClient
from telethon.sessions import StringSession
from mcp.server.fastmcp import FastMCP
from typing import Optional
from dotenv import load_dotenv

# Client will be initialized when needed
client: Optional[TelegramClient] = None

class TelegramServer:
    def __init__(self):
        self.app = FastMCP("telegram")
        self.client = None
        self.register_tools()
    
    async def initialize_client(self):
        """Initialize Telegram client if not already initialized"""
        if self.client and self.client.is_connected():
            return
        
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        session_string = os.getenv('TELEGRAM_SESSION_STRING')
        
        if not api_id or not api_hash or not session_string:
            raise ValueError("Missing Telegram credentials in .env file")
        
        self.client = TelegramClient(StringSession(session_string), api_id, api_hash)
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            raise ValueError("Session string is invalid or expired")
    
    def register_tools(self):
        """Register Telegram-related tools with the MCP server"""
        
        @self.app.tool()
        async def get_chats(page: int, page_size: int = 20, offset_id: int = 0, offset_date: str = None, offset_peer_id: int = None) -> str:
            """
            Used when checking messages. Gets a paginated list of chats from Telegram. 
            
            Args:
                page: Page number (1-indexed).
                page_size: Number of chats per page.
                offset_id: Message ID to use as offset for pagination (from previous page's last_message_id).
                offset_date: Date to use as offset for pagination (from previous page's last_message_date).
                offset_peer_id: Peer ID to use as offset for pagination (from previous page's last_peer_id).
            
            After using this tool, use get_messages to read the actual messages from chats
  with unread_count > 0
            """
            try:
                await self.initialize_client()
                # For page 1, start from the beginning
                if page == 1 or (offset_id == 0 and offset_date is None and offset_peer_id is None):
                    dialogs = await self.client.get_dialogs(limit=page_size, archived=False)
                else:
                    # For subsequent pages, use the provided offset parameters
                    offset_peer = None
                    if offset_peer_id:
                        # Get the peer entity from the ID
                        offset_peer = await self.client.get_entity(offset_peer_id)
                    
                    # Parse the offset date if provided
                    from datetime import datetime
                    offset_date_obj = None
                    if offset_date:
                        try:
                            offset_date_obj = datetime.fromisoformat(offset_date.replace('Z', '+00:00'))
                        except:
                            offset_date_obj = None
                    
                    dialogs = await self.client.get_dialogs(
                        limit=page_size,
                        offset_date=offset_date_obj,
                        offset_id=offset_id,
                        offset_peer=offset_peer,
                        archived=False
                    )
                
                result = []
                pagination_info = None
                
                for dialog in dialogs:
                    chat = {
                        "id": dialog.id,
                        "name": dialog.name,
                        "unread_count": dialog.unread_count,
                        "type": str(dialog.entity.__class__.__name__)
                    }
                    result.append(chat)
                    
                    # Store pagination info from the last dialog
                    if dialog == dialogs[-1] and dialog.message:
                        pagination_info = {
                            "last_message_id": dialog.message.id,
                            "last_message_date": dialog.date.isoformat() if dialog.date else None,
                            "last_peer_id": dialog.id
                        }
                
                # Return both results and pagination info
                response = {
                    "chats": result,
                    "page": page,
                    "page_size": page_size,
                    "has_more": len(result) == page_size
                }
                
                if pagination_info:
                    response["next_page_params"] = {
                        "page": page + 1,
                        "page_size": page_size,
                        "offset_id": pagination_info["last_message_id"],
                        "offset_date": pagination_info["last_message_date"],
                        "offset_peer_id": pagination_info["last_peer_id"]
                    }
                
                return json.dumps(response, indent=2)
            except Exception as e:
                return json.dumps({"error": str(e)})
                
        @self.app.tool()
        async def get_messages(chat_id: int, page: int, page_size: int = 20) -> str:
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
                await self.initialize_client()
                messages = await self.client.get_messages(chat_id, limit=limit, offset_id=0, offset_date=None, add_offset=offset)
                await self.client.send_read_acknowledge(entity=chat_id)
                
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
                return json.dumps({"error": str(e)})
            
        @self.app.tool()
        async def mark_messages_read(chat_id: int) -> str:
            """
            Mark all unread messages in a specific Telegram chat as read.
            
            Args:
                chat_id: The ID of the chat whose messages should be marked as read.
            """
            try:
                await self.initialize_client()
                # The read_history method marks messages as read
                result = await self.client.send_read_acknowledge(entity=chat_id)
                return json.dumps({
                    "success": True, 
                    "message": f"Successfully marked messages as read in chat {chat_id}"
                })
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
                
        @self.app.tool()
        async def send_message(chat_id: int, message: str, reply_to_msg_id: int = None) -> str:
            """
            Send a message to a specific chat in Telegram.
            
            Args:
                chat_id: The ID of the chat.
                message: The message content to send.
                reply_to_msg_id: Optional ID of a message to reply to. If provided, this message will be a reply to that specific message.
            """
            try:
                await self.initialize_client()
                result = await self.client.send_message(
                    entity=chat_id, 
                    message=message,
                    reply_to=reply_to_msg_id
                )
                return json.dumps({
                    "success": True, 
                    "message_id": result.id,
                    "is_reply": reply_to_msg_id is not None,
                    "replied_to_message_id": reply_to_msg_id
                })
            except Exception as e:
                return json.dumps({
                    "success": False, 
                    "error": str(e),
                    "is_reply": reply_to_msg_id is not None,
                    "replied_to_message_id": reply_to_msg_id
                })
        
        @self.app.tool()
        async def get_conversation_context(chat_id: int, message_count: int = 30) -> str:
            """
            This function retrieves recent messages from a specific chat to help
            understand the conversational style and tone, allowing it to
            generate responses that match the existing conversation pattern.
            The function also reads a user-defined style guide from convostyle.txt
            to further refine the response style.
            
            Args:
                chat_id: The ID of the chat to analyze.
                message_count: Number of recent messages to retrieve (default: 30).
            """
            try:
                await self.initialize_client()
                # Get messages from the chat
                messages = await self.client.get_messages(chat_id, limit=message_count)
                
                # Process and organize the conversation
                conversation = []
                sender_info = {}
                
                # First pass: collect unique senders and their information
                for msg in messages:
                    if msg.sender_id and msg.sender_id not in sender_info:
                        try:
                            # Get sender information
                            entity = await self.client.get_entity(msg.sender_id)
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
                except Exception as e:
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
                return json.dumps({
                    "error": str(e),
                    "message": "Failed to retrieve conversation context"
                })
    
    def run(self):
        """Run the MCP server"""
        self.app.run(transport='stdio')

def main():
    # Load .env file
    load_dotenv()
    
    # Get Telegram API credentials from .env file
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    session_string = os.getenv('TELEGRAM_SESSION_STRING')
    
    if not api_id or not api_hash:
        print("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH in your .env file", file=sys.stderr)
        print("Get these from https://my.telegram.org/apps", file=sys.stderr)
        sys.exit(1)
    
    if not session_string:
        print("Please set TELEGRAM_SESSION_STRING in your .env file", file=sys.stderr)
        print("Run: python telethon_auth.py to generate a session string", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Create and run server
        server = TelegramServer()
        server.run()
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()