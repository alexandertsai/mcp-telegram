"""Telegram client lifecycle, entity resolution and serialization helpers."""

import os
from typing import Optional, Union

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
)

# A chat/user can be referenced by numeric id, @username, phone number,
# t.me link or the literal "me".
EntityLike = Union[int, str]


class TelegramClientManager:
    """Owns a single long-lived Telethon client for the MCP process."""

    def __init__(self) -> None:
        self._client: Optional[TelegramClient] = None

    async def get_client(self) -> TelegramClient:
        """Return a connected, authorized client, (re)connecting as needed."""
        if self._client is None:
            api_id = os.getenv("TELEGRAM_API_ID")
            api_hash = os.getenv("TELEGRAM_API_HASH")
            session_string = os.getenv("TELEGRAM_SESSION_STRING")

            if not api_id or not api_hash or not session_string:
                raise ValueError(
                    "Missing Telegram credentials. Set TELEGRAM_API_ID, "
                    "TELEGRAM_API_HASH and TELEGRAM_SESSION_STRING."
                )
            self._client = TelegramClient(
                StringSession(session_string), int(api_id), api_hash
            )

        if not self._client.is_connected():
            await self._client.connect()
            if not await self._client.is_user_authorized():
                raise ValueError(
                    "Session string is invalid or expired. Re-run telegram-auth."
                )
        return self._client

    async def resolve(self, identifier: EntityLike):
        """Resolve a chat/user reference into a Telethon entity.

        Accepts a numeric id, ``@username``, phone number, t.me link or the
        literal ``"me"``. Raw numeric ids sometimes are not yet in Telethon's
        session cache, so we warm the cache from the dialog list and retry once.
        """
        client = await self.get_client()

        ident: EntityLike = identifier
        if isinstance(identifier, str):
            stripped = identifier.strip()
            if stripped.lower() == "me":
                return await client.get_me()
            try:
                ident = int(stripped)
            except ValueError:
                # @username, phone number or invite/t.me link
                return await client.get_entity(stripped)

        try:
            return await client.get_entity(ident)
        except (ValueError, TypeError):
            # The id is likely not cached yet; warm the cache and retry.
            await client.get_dialogs(limit=200)
            return await client.get_entity(ident)


def _media_info(message) -> Optional[dict]:
    """Summarize the media attached to a message, if any."""
    if message.media is None:
        return None

    info: dict = {"type": type(message.media).__name__}

    if message.photo is not None:
        info["kind"] = "photo"
    elif message.document is not None:
        doc = message.document
        info["kind"] = "document"
        info["mime_type"] = getattr(doc, "mime_type", None)
        info["size"] = getattr(doc, "size", None)
        for attr in getattr(doc, "attributes", []):
            if isinstance(attr, DocumentAttributeFilename):
                info["file_name"] = attr.file_name
            elif isinstance(attr, DocumentAttributeVideo):
                info["kind"] = "video"
                info["duration"] = attr.duration
            elif isinstance(attr, DocumentAttributeAudio):
                info["kind"] = "voice" if attr.voice else "audio"
                info["duration"] = attr.duration
            elif isinstance(attr, DocumentAttributeSticker):
                info["kind"] = "sticker"
    elif message.web_preview is not None:
        info["kind"] = "web_preview"
    elif message.geo is not None:
        info["kind"] = "geo"
    elif message.contact is not None:
        info["kind"] = "contact"
    elif message.poll is not None:
        info["kind"] = "poll"

    return info


def _reactions_info(message) -> Optional[list]:
    """Summarize reaction counts on a message, if any."""
    reactions = getattr(message, "reactions", None)
    if reactions is None or not getattr(reactions, "results", None):
        return None

    summary = []
    for result in reactions.results:
        emoticon = getattr(result.reaction, "emoticon", None)
        summary.append(
            {
                "reaction": emoticon or type(result.reaction).__name__,
                "count": result.count,
            }
        )
    return summary


def serialize_message(message) -> dict:
    """Convert a Telethon message into a JSON-serializable dict."""
    return {
        "id": message.id,
        "date": message.date.isoformat() if message.date else None,
        "text": message.text,
        "sender_id": message.sender_id,
        "reply_to_msg_id": message.reply_to_msg_id,
        "out": message.out,
        "edit_date": message.edit_date.isoformat() if message.edit_date else None,
        "views": getattr(message, "views", None),
        "forwarded": message.fwd_from is not None,
        "pinned": getattr(message, "pinned", False),
        "media": _media_info(message),
        "reactions": _reactions_info(message),
    }


def serialize_entity(entity) -> dict:
    """Convert a user/chat/channel entity into a JSON-serializable dict."""
    return {
        "id": getattr(entity, "id", None),
        "type": type(entity).__name__,
        "username": getattr(entity, "username", None),
        "first_name": getattr(entity, "first_name", None),
        "last_name": getattr(entity, "last_name", None),
        "title": getattr(entity, "title", None),
        "phone": getattr(entity, "phone", None),
        "bot": getattr(entity, "bot", None),
        "verified": getattr(entity, "verified", None),
        "participants_count": getattr(entity, "participants_count", None),
    }
