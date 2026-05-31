# Telegram MCP Server

Connect Claude to your Telegram account to read and send messages.

## Features

Most chats, users, and groups can be referenced by numeric id, `@username`,
phone number, t.me link, or the literal `"me"` — the server resolves them for
you (and warms Telethon's entity cache automatically so raw ids work too).

### Available Tools

**Reading**

- **get_me** – Info about the authenticated account
- **get_chats** – Paginated list of chats (names, ids, unread counts, pinned state); supports archived chats
- **get_messages** – Paginated message history for a chat (marks it read); includes media and reaction info
- **search_messages** – Search by text, globally or within a single chat
- **get_pinned_messages** – List pinned messages in a chat
- **get_entity_info** – Look up a user/group/channel by id, username, phone, or link
- **get_participants** – List members of a group or channel

**Sending & editing**

- **send_message** – Send text (Markdown), optionally as a reply
- **edit_message** – Edit a message you sent
- **delete_messages** – Delete messages (for everyone or just you)
- **forward_messages** – Forward messages between chats
- **send_reaction** – Add or clear an emoji reaction
- **pin_message** / **unpin_message** – Pin or unpin messages
- **mark_messages_read** – Mark a chat's unread messages as read

**Media**

- **send_file** – Send a photo, video, document, or voice note from disk
- **download_media** – Download a message's attached media to disk

**Contacts & users**

- **get_contacts** – List saved contacts
- **add_contact** / **delete_contact** – Manage contacts
- **block_user** / **unblock_user** – Block management

**Chat & channel management**

- **create_group** – Create a basic group
- **create_channel** – Create a channel or supergroup
- **join_chat** / **leave_chat** – Join (by username or invite link) or leave
- **archive_chat** – Archive / unarchive a chat
- **mute_chat** – Mute / unmute notifications

**Style-aware drafting**

- **get_conversation_context** – Recent messages + your `convostyle.txt` guide so Claude can match your texting style

## Setup Guide

### Step 1: Get Telegram API Credentials

1. Go to [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in and create an application
3. Save your **API ID** and **API Hash**

### Step 2: Install

```bash
# Clone the repository
git clone https://github.com/alexandertsai/mcp-telegram
cd mcp-telegram

# Set up Python environment
pip install uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync
```

### Step 3: Configure

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API credentials:
# TELEGRAM_API_ID=your_api_id_here
# TELEGRAM_API_HASH=your_api_hash_here
```

### Step 4: Authenticate

From the repository root:

```bash
uv run telegram-auth
```

Follow the prompts:
- Enter your phone number (with country code, e.g., +1234567890)
- Enter the code sent to your Telegram
- Enter your 2FA password if you have one

This writes `TELEGRAM_SESSION_STRING` to your `.env`.

### Step 5: Add to Claude Desktop

Find your Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add this configuration (replace the path with your clone's location):

```json
{
  "mcpServers": {
    "telegram": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-telegram", "run", "telegram-mcp"]
    }
  }
}
```

If `uv` isn't on Claude Desktop's `PATH`, use its absolute path (`which uv`).
Alternatively, point `command` at your venv's Python and use
`["-m", "mcp_telegram"]` as the args, with `cwd` set to the repo root.

Restart Claude Desktop.

## Usage

After setup, you can ask Claude to:
- "Check my Telegram messages"
- "Send a message to [contact name]"
- "What are my unread chats?"
- "Reply to the last message from [contact name]"

## Style Guide (Optional)

Create `src/mcp_telegram/convostyle.txt` to help Claude match your texting style:

```
I text casually with friends, formally with work contacts.
I use emojis sparingly and prefer short messages.
```

## Troubleshooting

### Authentication Issues

If authentication fails:
1. Check your API credentials in `.env`
2. Remove the TELEGRAM_SESSION_STRING line from `.env`
3. Run `uv run telegram-auth` again

### Common Errors

- **"Please set TELEGRAM_API_ID and TELEGRAM_API_HASH"**: Missing `.env` file or credentials
- **"Session string is invalid or expired"**: Re-run authentication
- **2FA password not showing**: This is normal - keep typing

## Requirements

- Python 3.10+
- Claude Desktop
- Telegram account

## License

Apache 2.0