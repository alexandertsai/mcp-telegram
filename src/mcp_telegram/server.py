"""MCP server exposing a broad set of Telegram tools via Telethon."""

import json
import os
from datetime import datetime, timedelta
from typing import List, Optional

from mcp.server.fastmcp import FastMCP
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    JoinChannelRequest,
    LeaveChannelRequest,
)
from telethon.tl.functions.contacts import (
    BlockRequest,
    DeleteContactsRequest,
    GetContactsRequest,
    ImportContactsRequest,
    UnblockRequest,
)
from telethon.tl.functions.messages import (
    CreateChatRequest,
    ImportChatInviteRequest,
    SendReactionRequest,
)
from telethon.tl.types import (
    InputNotifyPeer,
    InputPeerNotifySettings,
    InputPhoneContact,
    InputMessagesFilterPinned,
    ReactionEmoji,
)

from .client import (
    TelegramClientManager,
    serialize_entity,
    serialize_message,
)

mcp = FastMCP("telegram")
manager = TelegramClientManager()


def _ok(**fields) -> str:
    return json.dumps({"success": True, **fields}, indent=2, ensure_ascii=False, default=str)


def _err(error: Exception, **fields) -> str:
    return json.dumps(
        {"success": False, "error": str(error), **fields},
        indent=2,
        ensure_ascii=False,
        default=str,
    )


def _dump(payload) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


@mcp.tool()
async def get_me() -> str:
    """Get information about the currently authenticated Telegram account."""
    try:
        me = await manager.get_client()
        return _dump(serialize_entity(await me.get_me()))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_chats(
    page: int = 1,
    page_size: int = 20,
    offset_id: int = 0,
    offset_date: Optional[str] = None,
    offset_peer_id: Optional[int] = None,
    archived: bool = False,
) -> str:
    """List Telegram chats (dialogs), most recent first.

    Args:
        page: Page number (1-indexed).
        page_size: Number of chats per page.
        offset_id: Message id offset from a previous page's next_page_params.
        offset_date: Date offset (ISO string) from a previous page.
        offset_peer_id: Peer id offset from a previous page.
        archived: Whether to list archived chats instead of the main list.

    After this, use get_messages to read chats with unread_count > 0.
    """
    try:
        client = await manager.get_client()
        first_page = page == 1 or (
            offset_id == 0 and offset_date is None and offset_peer_id is None
        )

        if first_page:
            dialogs = await client.get_dialogs(limit=page_size, archived=archived)
        else:
            offset_peer = await manager.resolve(offset_peer_id) if offset_peer_id else None
            offset_date_obj = None
            if offset_date:
                try:
                    offset_date_obj = datetime.fromisoformat(
                        offset_date.replace("Z", "+00:00")
                    )
                except ValueError:
                    offset_date_obj = None
            dialogs = await client.get_dialogs(
                limit=page_size,
                offset_date=offset_date_obj,
                offset_id=offset_id,
                offset_peer=offset_peer,
                archived=archived,
            )

        chats = [
            {
                "id": d.id,
                "name": d.name,
                "unread_count": d.unread_count,
                "type": type(d.entity).__name__,
                "is_pinned": d.pinned,
            }
            for d in dialogs
        ]

        response = {
            "chats": chats,
            "page": page,
            "page_size": page_size,
            "has_more": len(dialogs) == page_size,
        }

        if dialogs:
            last = dialogs[-1]
            response["next_page_params"] = {
                "page": page + 1,
                "page_size": page_size,
                "offset_id": last.message.id if last.message else 0,
                "offset_date": last.date.isoformat() if last.date else None,
                "offset_peer_id": last.id,
            }

        return _dump(response)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_messages(chat: str, page: int = 1, page_size: int = 20) -> str:
    """Read paginated message history from a chat and mark it as read.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        page: Page number (1-indexed).
        page_size: Number of messages per page.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        messages = await client.get_messages(
            entity, limit=page_size, add_offset=(page - 1) * page_size
        )
        await client.send_read_acknowledge(entity)
        return _dump([serialize_message(m) for m in messages])
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def search_messages(
    query: str, chat: Optional[str] = None, limit: int = 30
) -> str:
    """Search messages by text, globally or within a single chat.

    Args:
        query: Text to search for.
        chat: Optional chat reference to limit the search to one conversation.
        limit: Maximum number of messages to return.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat) if chat else None
        messages = await client.get_messages(entity, search=query, limit=limit)
        return _dump([serialize_message(m) for m in messages])
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_pinned_messages(chat: str, limit: int = 20) -> str:
    """List pinned messages in a chat.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        limit: Maximum number of pinned messages to return.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        messages = await client.get_messages(
            entity, filter=InputMessagesFilterPinned, limit=limit
        )
        return _dump([serialize_message(m) for m in messages])
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_entity_info(identifier: str) -> str:
    """Look up a user, group or channel by id, @username, phone or t.me link.

    Args:
        identifier: id, @username, phone number, t.me link, or "me".
    """
    try:
        entity = await manager.resolve(identifier)
        return _dump(serialize_entity(entity))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_participants(chat: str, limit: int = 100, search: str = "") -> str:
    """List members of a group or channel.

    Args:
        chat: Group/channel reference (id, @username, or invite link).
        limit: Maximum number of participants to return.
        search: Optional name/username filter.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        participants = await client.get_participants(
            entity, limit=limit, search=search or ""
        )
        return _dump([serialize_entity(p) for p in participants])
    except Exception as e:  # noqa: BLE001
        return _err(e)


# --------------------------------------------------------------------------- #
# Sending / editing messages
# --------------------------------------------------------------------------- #


@mcp.tool()
async def send_message(
    chat: str, message: str, reply_to_msg_id: Optional[int] = None
) -> str:
    """Send a text message to a chat, optionally replying to a message.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message: Message text to send (supports Markdown).
        reply_to_msg_id: Optional message id to reply to.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        sent = await client.send_message(entity, message, reply_to=reply_to_msg_id)
        return _ok(message_id=sent.id, replied_to=reply_to_msg_id)
    except Exception as e:  # noqa: BLE001
        return _err(e, replied_to=reply_to_msg_id)


@mcp.tool()
async def edit_message(chat: str, message_id: int, new_text: str) -> str:
    """Edit the text of a message you previously sent.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message_id: Id of the message to edit.
        new_text: Replacement text.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        await client.edit_message(entity, message_id, new_text)
        return _ok(message_id=message_id)
    except Exception as e:  # noqa: BLE001
        return _err(e, message_id=message_id)


@mcp.tool()
async def delete_messages(
    chat: str, message_ids: List[int], revoke: bool = True
) -> str:
    """Delete one or more messages.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message_ids: Ids of the messages to delete.
        revoke: If True, delete for everyone (default); if False, only for you.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        await client.delete_messages(entity, message_ids, revoke=revoke)
        return _ok(deleted=message_ids)
    except Exception as e:  # noqa: BLE001
        return _err(e, message_ids=message_ids)


@mcp.tool()
async def forward_messages(
    from_chat: str, message_ids: List[int], to_chat: str
) -> str:
    """Forward messages from one chat to another.

    Args:
        from_chat: Source chat reference.
        message_ids: Ids of the messages to forward.
        to_chat: Destination chat reference.
    """
    try:
        client = await manager.get_client()
        source = await manager.resolve(from_chat)
        dest = await manager.resolve(to_chat)
        result = await client.forward_messages(dest, message_ids, source)
        forwarded = [m.id for m in (result if isinstance(result, list) else [result])]
        return _ok(forwarded_message_ids=forwarded)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def send_reaction(
    chat: str, message_id: int, emoji: str = "👍", big: bool = False
) -> str:
    """Add an emoji reaction to a message (empty emoji removes reactions).

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message_id: Id of the message to react to.
        emoji: Emoji to react with; pass "" to clear reactions.
        big: Whether to play the big/animated reaction.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        reaction = [ReactionEmoji(emoticon=emoji)] if emoji else None
        await client(
            SendReactionRequest(
                peer=entity, msg_id=message_id, big=big, reaction=reaction
            )
        )
        return _ok(message_id=message_id, emoji=emoji)
    except Exception as e:  # noqa: BLE001
        return _err(e, message_id=message_id)


@mcp.tool()
async def pin_message(chat: str, message_id: int, notify: bool = False) -> str:
    """Pin a message in a chat.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message_id: Id of the message to pin.
        notify: Whether to notify chat members.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        await client.pin_message(entity, message_id, notify=notify)
        return _ok(message_id=message_id)
    except Exception as e:  # noqa: BLE001
        return _err(e, message_id=message_id)


@mcp.tool()
async def unpin_message(chat: str, message_id: Optional[int] = None) -> str:
    """Unpin a specific message, or all pinned messages if none is given.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message_id: Id to unpin; omit to unpin everything.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        await client.unpin_message(entity, message_id)
        return _ok(message_id=message_id)
    except Exception as e:  # noqa: BLE001
        return _err(e, message_id=message_id)


@mcp.tool()
async def mark_messages_read(chat: str) -> str:
    """Mark all unread messages in a chat as read.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        await client.send_read_acknowledge(entity)
        return _ok(chat=chat)
    except Exception as e:  # noqa: BLE001
        return _err(e)


# --------------------------------------------------------------------------- #
# Media
# --------------------------------------------------------------------------- #


@mcp.tool()
async def send_file(
    chat: str,
    file_path: str,
    caption: str = "",
    reply_to_msg_id: Optional[int] = None,
    as_voice: bool = False,
) -> str:
    """Send a local file (photo, video, document, or voice note) to a chat.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        file_path: Absolute path to the file on disk.
        caption: Optional caption text.
        reply_to_msg_id: Optional message id to reply to.
        as_voice: Send an audio file as a voice note.
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No such file: {file_path}")
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        sent = await client.send_file(
            entity,
            file_path,
            caption=caption,
            reply_to=reply_to_msg_id,
            voice_note=as_voice,
        )
        return _ok(message_id=sent.id, file=file_path)
    except Exception as e:  # noqa: BLE001
        return _err(e, file=file_path)


@mcp.tool()
async def download_media(
    chat: str, message_id: int, download_dir: Optional[str] = None
) -> str:
    """Download the media attached to a message to local disk.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message_id: Id of the message whose media to download.
        download_dir: Directory to save into (defaults to current directory).
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        message = await client.get_messages(entity, ids=message_id)
        if message is None or message.media is None:
            raise ValueError("Message has no downloadable media.")
        target = download_dir or os.getcwd()
        os.makedirs(target, exist_ok=True)
        path = await client.download_media(message, file=target)
        return _ok(message_id=message_id, path=path)
    except Exception as e:  # noqa: BLE001
        return _err(e, message_id=message_id)


# --------------------------------------------------------------------------- #
# Contacts and users
# --------------------------------------------------------------------------- #


@mcp.tool()
async def get_contacts() -> str:
    """List the saved contacts on the account."""
    try:
        client = await manager.get_client()
        result = await client(GetContactsRequest(hash=0))
        return _dump([serialize_entity(u) for u in result.users])
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def add_contact(
    phone: str, first_name: str, last_name: str = ""
) -> str:
    """Add a phone number to your Telegram contacts.

    Args:
        phone: Phone number including country code.
        first_name: Contact's first name.
        last_name: Contact's last name (optional).
    """
    try:
        client = await manager.get_client()
        result = await client(
            ImportContactsRequest(
                contacts=[
                    InputPhoneContact(
                        client_id=0,
                        phone=phone,
                        first_name=first_name,
                        last_name=last_name,
                    )
                ]
            )
        )
        return _ok(imported=[serialize_entity(u) for u in result.users])
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def delete_contact(identifier: str) -> str:
    """Remove a user from your contacts.

    Args:
        identifier: id, @username, or phone of the contact to remove.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(identifier)
        await client(DeleteContactsRequest(id=[entity]))
        return _ok(removed=identifier)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def block_user(identifier: str) -> str:
    """Block a user.

    Args:
        identifier: id, @username, or phone of the user to block.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(identifier)
        await client(BlockRequest(id=entity))
        return _ok(blocked=identifier)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def unblock_user(identifier: str) -> str:
    """Unblock a previously blocked user.

    Args:
        identifier: id, @username, or phone of the user to unblock.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(identifier)
        await client(UnblockRequest(id=entity))
        return _ok(unblocked=identifier)
    except Exception as e:  # noqa: BLE001
        return _err(e)


# --------------------------------------------------------------------------- #
# Chat / group / channel management
# --------------------------------------------------------------------------- #


@mcp.tool()
async def create_group(title: str, users: List[str]) -> str:
    """Create a small (basic) group chat with the given users.

    Args:
        title: Group title.
        users: References (ids/@usernames/phones) of users to add.
    """
    try:
        client = await manager.get_client()
        members = [await manager.resolve(u) for u in users]
        await client(CreateChatRequest(users=members, title=title))
        return _ok(title=title, members=users)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def create_channel(
    title: str, about: str = "", megagroup: bool = False
) -> str:
    """Create a channel or supergroup.

    Args:
        title: Channel/supergroup title.
        about: Description text.
        megagroup: If True, create a supergroup; otherwise a broadcast channel.
    """
    try:
        client = await manager.get_client()
        result = await client(
            CreateChannelRequest(title=title, about=about, megagroup=megagroup)
        )
        chat = result.chats[0]
        return _ok(id=chat.id, title=chat.title)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def join_chat(identifier: str) -> str:
    """Join a public channel/group by @username or a private invite link.

    Args:
        identifier: @username, t.me link, or t.me/+hash invite link.
    """
    try:
        client = await manager.get_client()
        invite_hash = None
        if "joinchat/" in identifier:
            invite_hash = identifier.split("joinchat/", 1)[1]
        elif "/+" in identifier or identifier.startswith("+"):
            invite_hash = identifier.rsplit("+", 1)[1]

        if invite_hash:
            await client(ImportChatInviteRequest(invite_hash.strip("/")))
        else:
            entity = await manager.resolve(identifier)
            await client(JoinChannelRequest(entity))
        return _ok(joined=identifier)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def leave_chat(chat: str) -> str:
    """Leave a channel or supergroup.

    Args:
        chat: Channel/supergroup reference (id, @username, or invite link).
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        await client(LeaveChannelRequest(entity))
        return _ok(left=chat)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def archive_chat(chat: str, archive: bool = True) -> str:
    """Archive or unarchive a chat.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        archive: True to archive, False to move back to the main list.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        await client.edit_folder(entity, folder=1 if archive else 0)
        return _ok(chat=chat, archived=archive)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def mute_chat(chat: str, mute: bool = True) -> str:
    """Mute or unmute notifications for a chat.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        mute: True to mute, False to unmute.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        # Telegram uses a far-future mute_until to represent an indefinite mute.
        mute_until = datetime.now() + timedelta(days=365 * 10) if mute else None
        await client(
            UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(entity),
                settings=InputPeerNotifySettings(
                    mute_until=mute_until, silent=mute
                ),
            )
        )
        return _ok(chat=chat, muted=mute)
    except Exception as e:  # noqa: BLE001
        return _err(e)


# --------------------------------------------------------------------------- #
# Style-aware drafting
# --------------------------------------------------------------------------- #


@mcp.tool()
async def get_conversation_context(chat: str, message_count: int = 30) -> str:
    """Retrieve recent messages plus the user's style guide to draft replies
    that match their tone.

    Args:
        chat: Chat reference (id, @username, phone, or "me").
        message_count: Number of recent messages to retrieve.
    """
    try:
        client = await manager.get_client()
        entity = await manager.resolve(chat)
        messages = await client.get_messages(entity, limit=message_count)

        sender_names: dict = {}
        conversation = []
        for msg in reversed(messages):
            if not msg.text:
                continue
            if msg.sender_id not in sender_names:
                try:
                    sender = await client.get_entity(msg.sender_id)
                    sender_names[msg.sender_id] = (
                        getattr(sender, "first_name", None)
                        or getattr(sender, "title", None)
                        or f"User {msg.sender_id}"
                    )
                except Exception:  # noqa: BLE001
                    sender_names[msg.sender_id] = f"User {msg.sender_id}"
            conversation.append(
                {
                    "timestamp": msg.date.isoformat() if msg.date else None,
                    "sender_name": sender_names[msg.sender_id],
                    "is_self": msg.out,
                    "text": msg.text,
                    "message_id": msg.id,
                }
            )

        style_guide_path = os.path.join(os.path.dirname(__file__), "convostyle.txt")
        try:
            with open(style_guide_path, "r", encoding="utf-8") as fh:
                style_guide = fh.read().strip()
        except OSError:
            style_guide = "Style guide file not available. Focus on conversation history."

        return _dump(
            {
                "conversation": conversation,
                "user_style_guide": style_guide,
                "analysis_instructions": (
                    "Read the user_style_guide first, then study the conversation "
                    "history for tone, length, emoji/slang usage and greetings. "
                    "Draft a reply that matches both; when they conflict, the "
                    "explicit style guide wins."
                ),
            }
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


def run() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")
