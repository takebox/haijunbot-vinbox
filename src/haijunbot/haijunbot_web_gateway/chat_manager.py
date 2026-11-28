"""Chat room management module.

Manages the state and logic of chat rooms, client registration, private chat sessions, etc.
Supports chat room persistence, automatically restored after a gateway restart.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import WebSocket


class ChatManager:
    """Chat room manager.

    Maintains the state of chat rooms, clients, private chat sessions, etc., and handles all chat_* message types.
    """

    def __init__(
        self, data_dir: Optional[str] = None, user_manager: Optional[Any] = None
    ) -> None:
        self._data_dir = data_dir
        self._user_manager = user_manager
        self._chat_rooms: Dict[
            str, Dict[str, Any]
        ] = {}  # room_id -> {name, members: set[user_id], created_by, created_at}
        self._chat_clients: Dict[
            str, Dict[str, Any]
        ] = {}  # client_id -> {name, connection_id, websocket, user_id}
        self._chat_private_sessions: Dict[
            str, Dict[str, Any]
        ] = {}  # session_id -> {client_a, client_b, messages: list}
        self._chat_room_seq = 0  # Chat room ID auto-increment
        self._chat_private_seq = 0  # Private chat session ID auto-increment
        self._lock = asyncio.Lock()
        # Load persisted data at startup
        self._load_rooms()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _get_rooms_file(self) -> str:
        """Get the chat room persistence file path."""
        if not self._data_dir:
            return ""
        return os.path.join(self._data_dir, "chat_rooms.json")

    def _load_rooms(self) -> None:
        """Load chat room data from the JSON file."""
        filepath = self._get_rooms_file()
        if not filepath or not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            max_seq = 0
            for room_id, room_data in data.items():
                members = set(room_data.get("members", []))
                self._chat_rooms[room_id] = {
                    "name": room_data.get("name", "Unnamed"),
                    "members": members,  # set of user_ids
                    "created_by": room_data.get("created_by", ""),
                    "created_at": room_data.get("created_at", 0),
                }
                # Restore the auto-increment sequence number
                try:
                    seq = int(room_id.split("_")[1]) if "_" in room_id else 0
                    if seq > max_seq:
                        max_seq = seq
                except (ValueError, IndexError):
                    pass
            self._chat_room_seq = max_seq
            print(f"[CHAT] Loaded {len(self._chat_rooms)} rooms from {filepath}")
        except Exception as e:
            print(f"[CHAT] Failed to load rooms: {e}")

    def _save_rooms(self) -> None:
        """Save chat room data to the JSON file."""
        filepath = self._get_rooms_file()
        if not filepath:
            return
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            data = {}
            for room_id, room in self._chat_rooms.items():
                data[room_id] = {
                    "name": room["name"],
                    "members": list(room["members"]),  # convert set to list for serialization
                    "created_by": room["created_by"],
                    "created_at": room["created_at"],
                }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CHAT] Failed to save rooms: {e}")

    def get_user_rooms(self, user_id: str) -> List[str]:
        """Get the list of chat room IDs the user has joined."""
        joined = []
        for room_id, room in self._chat_rooms.items():
            if user_id in room["members"]:
                joined.append(room_id)
        return joined

    # ------------------------------------------------------------------
    # Client registration
    # ------------------------------------------------------------------

    async def register_client(
        self,
        client_id: str,
        name: str,
        connection_id: str,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a client and broadcast an online notification."""
        print(f"[CHAT REGISTER] client_id={client_id} name={name} user_id={user_id}")
        async with self._lock:
            self._chat_clients[client_id] = {
                "name": name,
                "display_name": display_name or name,
                "connection_id": connection_id,
                "websocket": websocket,
                "registered_at": time.time(),
                "user_id": user_id,
            }
        # Broadcast the online notification (executed outside the lock to avoid deadlock)
        await self.broadcast_to_all(
            {
                "type": "chat_client_joined",
                "payload": {
                    "client_id": client_id,
                    "user_id": user_id or client_id,
                    "name": name,
                    "display_name": display_name or name,
                },
            },
            exclude_client_id=client_id,
        )
        return {
            "success": True,
            "client_id": client_id,
            "user_id": user_id or client_id,
            "name": name,
            "display_name": display_name or name,
        }

    async def unregister_client(self, client_id: str) -> None:
        """Unregister a client and broadcast an offline notification.
        Note: the user_id is not removed from room members, preserving the persistent membership.
        """
        client_info = None
        user_id = None
        async with self._lock:
            client_info = self._chat_clients.pop(client_id, None)
            if client_info:
                user_id = client_info.get("user_id")
            # Do not remove the user_id from chat room members, preserving persistence
        # Broadcast the offline notification (executed outside the lock to avoid deadlock)
        if client_info:
            still_online = False
            if user_id:
                still_online = any(
                    info.get("user_id") == user_id
                    for info in self._chat_clients.values()
                )
            await self.broadcast_to_all(
                {
                    "type": "chat_client_left",
                    "payload": {
                        "client_id": client_id,
                        "name": client_info.get("name", ""),
                        "user_id": user_id or client_id,
                        "still_online": still_online,
                    },
                },
            )
            # [Added] Broadcast a member update notification to the rooms the user is in
            if user_id:
                for room_id, room in self._chat_rooms.items():
                    if user_id in room["members"]:
                        await self.broadcast_to_room(
                            room_id,
                            {
                                "type": "chat_room_members_update",
                                "payload": {
                                    "room_id": room_id,
                                    "user_id": user_id,
                                    "online": still_online,
                                },
                            },
                        )

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client information."""
        return self._chat_clients.get(client_id)

    def get_client_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get online client information by user_id. Prefers the most recently registered client."""
        latest = None
        for cid, info in self._chat_clients.items():
            if info.get("user_id") == user_id:
                if latest is None or info.get("registered_at", 0) > latest.get(
                    "registered_at", 0
                ):
                    latest = {"client_id": cid, **info}
        return latest

    def get_sessions(self) -> List[Dict[str, Any]]:
        """Get all active sessions (one per connection, no deduplication), with the corresponding user information attached."""
        sessions: List[Dict[str, Any]] = []
        for cid, info in self._chat_clients.items():
            user_id = info.get("user_id") or cid
            username = None
            display_name = info.get("display_name") or info.get("name")
            if self._user_manager and info.get("user_id"):
                user = self._user_manager.get_user(info["user_id"])
                if user:
                    username = user.get("username")
                    display_name = user.get("display_name") or username
            sessions.append(
                {
                    "session_id": cid,
                    "client_id": cid,
                    "user_id": user_id,
                    "username": username,
                    "name": info.get("name", ""),
                    "display_name": display_name or "",
                    "connection_id": info.get("connection_id", ""),
                    "registered_at": info.get("registered_at", 0),
                }
            )
        return sessions

    def get_clients(self) -> list[Dict[str, Any]]:
        """Get the list of all online clients (deduplicated by user_id; multiple devices of the same user are shown only once)."""
        user_map: Dict[str, Dict[str, Any]] = {}  # user_id -> aggregated information
        for cid, info in self._chat_clients.items():
            uid = info.get("user_id") or cid
            if uid in user_map:
                # Multiple devices of the same user; increment the device count
                user_map[uid]["client_count"] += 1
            else:
                user_map[uid] = {
                    "client_id": cid,
                    "name": info["name"],
                    "display_name": info.get("display_name", info["name"]),
                    "user_id": uid,
                    "client_count": 1,
                }
        return list(user_map.values())

    async def broadcast_to_all(
        self,
        message: Dict[str, Any],
        exclude_client_id: Optional[str] = None,
    ) -> None:
        """Broadcast a message to all online clients."""
        for client_id, client in self._chat_clients.items():
            if client_id == exclude_client_id:
                continue
            if client and client["websocket"]:
                try:
                    await client["websocket"].send_json(message)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Chat rooms
    # ------------------------------------------------------------------

    async def create_room(
        self, name: str, creator_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a chat room. members uses user_id."""
        member_id = user_id or creator_id
        async with self._lock:
            self._chat_room_seq += 1
            room_id = f"room_{self._chat_room_seq}"
            self._chat_rooms[room_id] = {
                "name": name,
                "members": {member_id},
                "created_by": member_id,
                "created_at": time.time(),
            }
            self._save_rooms()
        return {"success": True, "room_id": room_id, "name": name}

    def get_rooms(self) -> list[Dict[str, Any]]:
        """Get the list of all chat rooms."""
        return [
            {
                "room_id": rid,
                "name": room["name"],
                "member_count": len(room["members"]),
                "created_by": room["created_by"],
            }
            for rid, room in self._chat_rooms.items()
        ]

    async def join_room(self, room_id: str, client_id: str) -> Dict[str, Any]:
        """Join a chat room. Adds the user_id to members."""
        async with self._lock:
            room = self._chat_rooms.get(room_id)
            if not room:
                return {"success": False, "error": "Chat room does not exist"}
            # Look up user_id from client_id
            client = self._chat_clients.get(client_id)
            user_id = client.get("user_id") if client else None
            member_id = user_id or client_id
            print(
                f"[CHAT JOIN] room={room_id} client_id={client_id} user_id={user_id} member_id={member_id} existing_members={room['members']}"
            )
            room["members"].add(member_id)
            self._save_rooms()
        return {"success": True, "room_id": room_id, "name": room["name"]}

    async def leave_room(self, room_id: str, client_id: str) -> Dict[str, Any]:
        """Leave a chat room. Removes the user_id from members."""
        async with self._lock:
            room = self._chat_rooms.get(room_id)
            if not room:
                return {"success": False, "error": "Chat room does not exist"}
            # Look up user_id from client_id
            client = self._chat_clients.get(client_id)
            user_id = client.get("user_id") if client else None
            member_id = user_id or client_id
            room["members"].discard(member_id)
            self._save_rooms()
        return {"success": True, "room_id": room_id}

    async def rename_room(
        self, room_id: str, client_id: str, new_name: str
    ) -> Dict[str, Any]:
        """Rename a chat room (only the creator can rename)."""
        if not new_name or not new_name.strip():
            return {"success": False, "error": "Chat room name cannot be empty"}
        async with self._lock:
            room = self._chat_rooms.get(room_id)
            if not room:
                return {"success": False, "error": "Chat room does not exist"}
            # Look up user_id from client_id; only the creator and admins can rename
            client = self._chat_clients.get(client_id)
            user_id = client.get("user_id") if client else None
            member_id = user_id or client_id
            is_admin = False
            if user_id and self._user_manager:
                user_data = self._user_manager.get_user(user_id)
                is_admin = bool(user_data and user_data.get("is_admin", False))
            if room["created_by"] != member_id and not is_admin:
                return {"success": False, "error": "Only the creator and admins can rename the chat room"}
            old_name = room["name"]
            room["name"] = new_name.strip()
            self._save_rooms()
        return {
            "success": True,
            "room_id": room_id,
            "old_name": old_name,
            "new_name": room["name"],
        }

    async def delete_room(self, room_id: str, client_id: str) -> Dict[str, Any]:
        """Delete a chat room (only the creator and admins can delete). Returns the deleted room's member list for notifications."""
        async with self._lock:
            room = self._chat_rooms.get(room_id)
            if not room:
                return {"success": False, "error": "Chat room does not exist"}
            # Look up user_id from client_id to compare with created_by
            client = self._chat_clients.get(client_id)
            user_id = client.get("user_id") if client else None
            member_id = user_id or client_id
            is_admin = False
            if user_id and self._user_manager:
                user_data = self._user_manager.get_user(user_id)
                is_admin = bool(user_data and user_data.get("is_admin", False))
            if room["created_by"] != member_id and not is_admin:
                return {"success": False, "error": "Only the creator and admins can delete the chat room"}
            members = list(room["members"])
            del self._chat_rooms[room_id]
            self._save_rooms()
        return {
            "success": True,
            "room_id": room_id,
            "name": room["name"],
            "members": members,
        }

    def get_room_members(self, room_id: str) -> list[Dict[str, Any]]:
        """Get the chat room member list (with detailed information). members stores user_id, so the online client must be looked up."""
        room = self._chat_rooms.get(room_id)
        if not room:
            return []
        members = []
        for uid in room["members"]:
            # Look up the online client
            client = self.get_client_by_user_id(uid)
            if client:
                # [Modified] Add an online flag and device count for online members
                device_count = sum(
                    1
                    for info in self._chat_clients.values()
                    if info.get("user_id") == uid
                )
                members.append(
                    {
                        "client_id": client["client_id"],
                        "name": client["name"],
                        "display_name": client.get("display_name", client["name"]),
                        "user_id": uid,
                        "online": True,
                        "device_count": device_count,
                    }
                )
            else:
                # Offline users are also shown (username queried via user_manager)
                user_name = uid
                user_display_name = ""
                if self._user_manager:
                    user_data = self._user_manager.get_user(uid)
                    if user_data:
                        user_name = user_data.get("username", uid)
                        user_display_name = user_data.get("display_name", "")
                members.append(
                    {
                        "user_id": uid,
                        "name": user_name,
                        "display_name": user_display_name or user_name,
                        "online": False,
                    }
                )
        return members

    # ------------------------------------------------------------------
    # Message broadcasting
    # ------------------------------------------------------------------

    async def broadcast_to_room(
        self,
        room_id: str,
        message: Dict[str, Any],
        exclude_client_id: Optional[str] = None,
    ) -> None:
        """Broadcast a message to all chat room members. members stores user_id, so the online client must be looked up."""
        room = self._chat_rooms.get(room_id)
        if not room:
            print(f"[CHAT BROADCAST] room {room_id} not found")
            return
        # Get the excluded client's user_id
        exclude_user_id = None
        if exclude_client_id:
            ex_client = self._chat_clients.get(exclude_client_id)
            exclude_user_id = ex_client.get("user_id") if ex_client else None
        print(
            f"[CHAT BROADCAST] room={room_id} members={room['members']} exclude_uid={exclude_user_id}"
        )
        for uid in room["members"]:
            if uid == exclude_user_id:
                print(f"[CHAT BROADCAST] skip excluded uid={uid}")
                continue
            # Look up the online client
            client = self.get_client_by_user_id(uid)
            print(
                f"[CHAT BROADCAST] uid={uid} client_found={client is not None} has_ws={client.get('websocket') is not None if client else 'N/A'}"
            )
            if client and client.get("websocket"):
                try:
                    await client["websocket"].send_json(message)
                    print(
                        f"[CHAT BROADCAST] sent to uid={uid} client_id={client.get('client_id')}"
                    )
                except Exception as e:
                    print(f"[CHAT BROADCAST] FAILED to send to uid={uid}: {e}")

    # ------------------------------------------------------------------
    # Private chat
    # ------------------------------------------------------------------

    async def send_private(
        self, sender_id: str, receiver_id: str, content: str, image_url: str = ""
    ) -> Dict[str, Any]:
        """Send a private chat message (supports receiving on multiple devices)."""
        if sender_id not in self._chat_clients:
            return {"success": False, "error": "Sender is not registered"}
        # [Modified] Online check compatible with user_id: find any online device by client_id or user_id
        receiver_online = any(
            info.get("user_id") == receiver_id or cid == receiver_id
            for cid, info in self._chat_clients.items()
        )
        if not receiver_online:
            return {"success": False, "error": "Receiver is offline"}

        # Uniformly use user_id as the session identifier to avoid client_id inconsistency from multiple devices/reconnects of the same user
        sender_user_id: str = self._chat_clients[sender_id].get("user_id") or sender_id
        receiver_user_id: str = receiver_id
        for cid, info in self._chat_clients.items():
            if info.get("user_id") == receiver_id or cid == receiver_id:
                receiver_user_id = info.get("user_id") or cid
                break

        # Find or create a private chat session
        session_id = self._find_private_session(sender_user_id, receiver_user_id)
        if not session_id:
            async with self._lock:
                self._chat_private_seq += 1
                session_id = f"private_{self._chat_private_seq}"
                self._chat_private_sessions[session_id] = {
                    "client_a": sender_user_id,
                    "client_b": receiver_user_id,
                    "messages": [],
                }

        # Save the message
        msg = {
            "sender_id": sender_id,
            "sender_user_id": sender_user_id,
            "sender_name": self._chat_clients[sender_id]["name"],
            "sender_display_name": self._chat_clients[sender_id].get(
                "display_name", self._chat_clients[sender_id]["name"]
            ),
            "content": content,
            "timestamp": time.time(),
        }
        if image_url:
            msg["image_url"] = image_url
        self._chat_private_sessions[session_id]["messages"].append(msg)

        # [Added] Find all online devices by user_id and broadcast
        # Send the message to all devices matching user_id
        sent_count = 0
        for cid, info in self._chat_clients.items():
            if info.get("user_id") == receiver_user_id:
                if info["websocket"]:
                    try:
                        await info["websocket"].send_json(
                            {
                                "type": "chat_private_message",
                                "payload": {
                                    "session_id": session_id,
                                    "sender_user_id": sender_user_id,
                                    "message": msg,
                                },
                            }
                        )
                        sent_count += 1
                    except Exception:
                        pass

        return {
            "success": True,
            "session_id": session_id,
            "message": msg,
            "sent_count": sent_count,
        }

    def get_private_history(self, user_id: str, other_id: str) -> Dict[str, Any]:
        """Get private chat history messages.

        All parameters are user_id: private chat sessions uniformly use user_id as the identifier (see send_private).
        """
        session_id = self._find_private_session(user_id, other_id)
        if not session_id:
            return {"success": True, "messages": []}
        return {
            "success": True,
            "session_id": session_id,
            "messages": self._chat_private_sessions[session_id]["messages"],
        }

    def _find_private_session(self, user_a: str, user_b: str) -> Optional[str]:
        """Find the private chat session between two users (matched by user_id)."""
        for sid, session in self._chat_private_sessions.items():
            if (session["client_a"] == user_a and session["client_b"] == user_b) or (
                session["client_a"] == user_b and session["client_b"] == user_a
            ):
                return sid
        return None
