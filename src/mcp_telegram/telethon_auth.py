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
from dotenv import load_dotenv, set_key

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(message)s',
    datefmt='%m/%d/%y %H:%M:%S',
)
logger = logging.getLogger(__name__)

async def authenticate():
    # Load existing .env file
    load_dotenv()
    
    # Get API credentials from .env
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')
    password = os.getenv('TELEGRAM_2FA_PASSWORD')  # Optional, for 2FA
    session_string = os.getenv('TELEGRAM_SESSION_STRING')
    
    # Check if we already have a valid session
    if session_string:
        logger.info("Found existing session string in .env file. Verifying...")
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.info("✓ Existing session is valid! You're already authenticated.")
                await client.disconnect()
                return True
            else:
                logger.warning("Existing session is invalid or expired. Need to re-authenticate.")
        except Exception as e:
            logger.warning(f"Error with existing session: {str(e)}")
        finally:
            await client.disconnect()
    
    # Check required credentials
    if not api_id or not api_hash:
        logger.error("Missing required credentials in .env file!")
        logger.error("Please add the following to your .env file:")
        logger.error("TELEGRAM_API_ID=your_api_id")
        logger.error("TELEGRAM_API_HASH=your_api_hash")
        logger.error("Get these from https://my.telegram.org/apps")
        return False
    
    # Get phone number if not in .env
    if not phone:
        phone = input("Enter your phone number (with country code, e.g. +12345678900): ")
        # Save phone to .env for future use
        env_path = os.path.join(os.getcwd(), '.env')
        set_key(env_path, 'TELEGRAM_PHONE', phone)
        logger.info(f"Phone number saved to .env file")
    else:
        logger.info(f"Using phone number from .env: {phone}")
        use_saved = input(f"Use saved phone number {phone}? (y/n): ").lower()
        if use_saved != 'y':
            phone = input("Enter your phone number (with country code, e.g. +12345678900): ")
            env_path = os.path.join(os.getcwd(), '.env')
            set_key(env_path, 'TELEGRAM_PHONE', phone)
    
    # Create new session
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    try:
        await client.connect()
        
        # Send code request
        logger.info(f"Sending authentication code to {phone}...")
        await client.send_code_request(phone)
        
        # Get the code from the user
        code = input("Enter the code you received: ")
        
        # Initialize save_pwd to avoid reference error
        save_pwd = 'n'
        
        try:
            # Try to sign in with the code
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            # 2FA is enabled
            logger.info("Two-factor authentication is enabled.")
            
            # Try to use saved password first
            if password:
                logger.info("Using 2FA password from .env file...")
                try:
                    await client.sign_in(password=password)
                    logger.info("✓ Successfully authenticated with saved password!")
                except Exception as e:
                    logger.warning("Saved password didn't work, please enter manually.")
                    password = None
            
            # If no saved password or it didn't work, ask user
            if not password:
                password = getpass.getpass("Enter your 2FA password: ")
                await client.sign_in(password=password)
                
                # Ask if user wants to save password
                save_pwd = input("Save 2FA password to .env file for future use? (y/n): ").lower()
                if save_pwd == 'y':
                    env_path = os.path.join(os.getcwd(), '.env')
                    set_key(env_path, 'TELEGRAM_2FA_PASSWORD', password)
                    logger.info("2FA password saved to .env file")
        
        if await client.is_user_authorized():
            # Save the string session to .env
            session_string = client.session.save()
            env_path = os.path.join(os.getcwd(), '.env')
            set_key(env_path, 'TELEGRAM_SESSION_STRING', session_string)
            
            logger.info("✓ Authentication successful!")
            logger.info("✓ Session string saved to .env file")
            logger.info("")
            logger.info("You can now start the MCP server with: python main.py")
            logger.info("")
            logger.info("Your .env file has been updated with:")
            logger.info("- TELEGRAM_SESSION_STRING (required)")
            logger.info("- TELEGRAM_PHONE (for convenience)")
            if save_pwd == 'y':
                logger.info("- TELEGRAM_2FA_PASSWORD (optional, for automatic re-auth)")
            
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
    logger.info("Telegram MCP Authentication Setup")
    logger.info("-" * 40)
    
    # Check if .env file exists
    env_path = os.path.join(os.getcwd(), '.env')
    if not os.path.exists(env_path):
        logger.info("No .env file found. Creating one...")
        with open(env_path, 'w') as f:
            f.write("# Telegram MCP Configuration\n")
            f.write("# Get API credentials from https://my.telegram.org/apps\n")
            f.write("TELEGRAM_API_ID=\n")
            f.write("TELEGRAM_API_HASH=\n")
            f.write("TELEGRAM_PHONE=\n")
            f.write("TELEGRAM_2FA_PASSWORD=\n")
            f.write("TELEGRAM_SESSION_STRING=\n")
        logger.info(f"Created .env file at: {env_path}")
        logger.info("Please edit it and add your TELEGRAM_API_ID and TELEGRAM_API_HASH")
        logger.info("Then run this script again.")
        sys.exit(1)
    
    success = asyncio.run(authenticate())
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()