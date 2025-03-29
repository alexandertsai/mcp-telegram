#!/usr/bin/env python3
# telethon_auth.py

import asyncio
import os
import sys
import logging
import getpass
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(message)s',
    datefmt='%m/%d/%y %H:%M:%S',
)
logger = logging.getLogger(__name__)

async def authenticate():
    # Get API credentials
    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')
    
    if not api_id or not api_hash:
        logger.error("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables")
        return False
    
    # Get phone number
    phone = input("Enter your phone number (with country code, e.g. +12345678900): ")
    
    # Create session file in a known location specific to this phone
    session_path = os.path.expanduser(f"~/.telegram_mcp_{phone}")
    
    # Use StringSession for more reliable storage
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    try:
        await client.connect()
        
        if await client.is_user_authorized():
            # Save the string session to a file
            session_string = client.session.save()
            session_string_file = f"{session_path}.string"
            with open(session_string_file, 'w') as f:
                f.write(session_string)
            logger.info(f"Already authenticated! Session string saved to {session_string_file}")
            
            # Also save the traditional session for compatibility
            traditional_client = TelegramClient(session_path, api_id, api_hash)
            await traditional_client.connect()
            await traditional_client.disconnect()
            
            return True
        
        # Send code request
        await client.send_code_request(phone)
        
        # Get the code from the user
        code = input("Enter the code you received: ")
        
        try:
            # Try to sign in with the code
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            # 2FA is enabled, ask for password
            logger.info("Two-factor authentication is enabled.")
            password = getpass.getpass("Enter your 2FA password: ")
            await client.sign_in(password=password)
        
        if await client.is_user_authorized():
            # Save the string session to a file
            session_string = client.session.save()
            session_string_file = f"{session_path}.string"
            with open(session_string_file, 'w') as f:
                f.write(session_string)
            
            # Also save the traditional session for compatibility
            traditional_client = TelegramClient(session_path, api_id, api_hash)
            await traditional_client.connect()
            if await traditional_client.is_user_authorized():
                await traditional_client.disconnect()
            
            logger.info(f"Authentication successful! Session saved to:")
            logger.info(f"1. String session: {session_string_file}")
            logger.info(f"2. Traditional session: {session_path}.session")
            logger.info(f"You can now start the MCP server.")
            return True
        else:
            logger.error("Authentication failed.")
            return False
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return False
    finally:
        await client.disconnect()

def main():
    success = asyncio.run(authenticate())
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()