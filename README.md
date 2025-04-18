# Telegram MCP Server

This is a simple MCP server that lets Claude access your Telegram account to read and send messages.

## Functions

1. **`get_chats`**: Get a list of your Telegram chats
2. **`send_message`**: Send a message to a chat
2. **`get_message`**: Gets messages from a chat and prints the unread messages
3. **`mark_messages_read`**: Mark messages as read
4. **`get_conversation_context`**: Gets past 20 messages and reads `convostyle.txt` to determine an appropriate reply


## Setup

### Recommended set up

### Step 1: Get Your Telegram API Credentials

1. Go to [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in and create an application (or use an existing one)
Note: It doesn't matter what kind of application - just create anything... make sure to select "web" under the type.
3. Note down your **API ID** and **API Hash**

### Step 2: Set Up Python Environment

Install the required packages (open your terminal to do this. command+space on mac and key in 'terminal' or on windows hit the windows key and key in 'terminal'. Copy and paste the code into the terminal line by line). Ensure you have installed Git beforehand.

```bash
# Clone the repository within your desired directory (if you haven't already)
git clone https://github.com/alexandertsai/mcp-telegram
cd mcp-telegram
```

Set up the virtual environment. Use `pip3` instead if applicable.
```bash
# Set up virtual environment
pip install uv
uv venv
source .venv/bin/activate
# .venv\Scripts\activate for windows
uv add mcp-sdk telethon python-dotenv nest_asyncio
```

### Step 3: Add IDs

**For Mac (bash):**

In the virtual environment, run the following:
```bash
export TELEGRAM_PHONE=phone number with country code and no spaces
export TELEGRAM_API_ID=api_id
export TELEGRAM_API_HASH=api_hash
```

Check to see if they have been exported with `printenv` in terminal.

**For Windows (Powershell):**

In the virtual environment, run the following. Make sure to include the quotation marks otherwise powershell may struggle:
```powershell
$env:TELEGRAM_PHONE="phone number with country code and no spaces"
$env:TELEGRAM_API_ID="api_id"
$env:TELEGRAM_API_HASH="api_hash"
```

Check to see if they have been exported with `gci env:` in powershell.

### Step 4: Run authentication

Run this to authenticate. If you have 2FA, when typing in your password you will not see any text appear in the terminal. This is normal! Try not to make a typo during 2FA - it makes you restart the entire process if you do... Use `python` or `python3` depending on which you have installed.:

```bash
cd src/mcp_telegram
python3 telethon_auth.py
```

You'll be asked for:
- Your phone number (in international format with +) (do not leave any spaces)
- The code Telegram sends to your account
- Your 2FA password (if enabled)

This creates a session file in your home directory so you don't need to authenticate again.

### Step 5: Add to Claude Desktop

Edit your Claude Desktop configuration:

Open Claude desktop, go to settings (cmd+,), click on Developer and then Edit Config. Edit the claude)desktop_config.json file. Make sure developer mode is enabled. 

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`


Add this to your config (replace with your actual credentials). Press command+s to save. :

```json
"mcpServers": {
      "telegram": {
      "command": "/your/path/to/python3",
      "args": ["/full/path/to/mcp-telegram/main.py"],
      "env": {
          "TELEGRAM_API_ID": "your_api_id_here",
          "TELEGRAM_API_HASH": "your_api_hash_here",
          "TELEGRAM_PHONE": "+65945678900"
          }
      }
  }
```

**main.py:**
To get the full path, go to your IDE or desktop, find the file, right click on it, and click "COPY PATH".

**python:**
Run `where.exe python` (Windows) or `where python` (Mac) in your terminal to get the full path (replace with `python3` if needed). If on Windows, you may need to replace the backslashes in your path with forward slash because of JSON formatting (ctrl+f "\\", replace all (ctrl + h) with "/").

### VERY IMPORTANT:
1. Use the full absolute path to both Python and the main.py script
2. Replace API credentials with your actual values from Step 1
3. Set your phone number in international format

### Step 6 (optional):

Feel free to configure `convostyle.txt` in `src/mcp_telegram` if you want the chatbot to respond and sound like you.

## That's It!

Restart Claude Desktop (quit and reopen), and you can now ask Claude to:
- Show your recent Telegram chats
- Read messages from specific chats
- Mark certain messages as "read"
- Send messages to your contacts or groups while sounding natural

Make sure to include the word "Telegram" when asking Claude a prompt or it might not understand. For example, "Claude do I have any unread telegram messages?"

## Customisation

You can go under Claude Desktop -> click on your user then settings in the bottom left -> configure your personal preferences to get more tailored responses. For example "When using MCP to check Telegram, ignore channels". 

## Pesky troubleshooting
While in the virtual environment, try running:
```bash
ls -la ~/.mcp_telegram_*
```
Then terminate your session files with (just copy and paste the path of the files with rm in front)
```bash
rm /Users/username/.mcp_telegram_numberininternationalformat*
```
Try step 3 again.
