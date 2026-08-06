"""
Digital Campus - Chat Endpoints
WebSocket real-time messaging + REST for history & offline sync.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.models import ChatMember, ChatMessage, ChatRoom, User
from app.schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatMessageWithUser,
    ChatRoomCreate,
    ChatRoomResponse,
    ChatRoomWithMembers,
    ChatSyncPayload,
    UserResponse,
)

router = APIRouter()


# ──────────────────────────────────────────────
# WEBSOCKET CONNECTION MANAGER
# ──────────────────────────────────────────────


class ConnectionManager:
    """Manages WebSocket connections per chat room."""

    def __init__(self):
        # room_id → {user_id: websocket}
        self.active_connections: dict[int, dict[int, WebSocket]] = {}

    async def connect(self, room_id: int, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][user_id] = websocket

    def disconnect(self, room_id: int, user_id: int):
        if room_id in self.active_connections:
            self.active_connections[room_id].pop(user_id, None)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, room_id: int, message: dict):
        """Send message to all connected users in a room."""
        if room_id in self.active_connections:
            for ws in self.active_connections[room_id].values():
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    def get_online_users(self, room_id: int) -> list[int]:
        return list(self.active_connections.get(room_id, {}).keys())


manager = ConnectionManager()


def _authenticate_ws_token(token: str) -> Optional[User]:
    """Validate JWT from WebSocket query param and return user."""
    db = SessionLocal()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
        return db.query(User).filter(User.email == email).first()
    except JWTError:
        return None
    finally:
        db.close()


# ──────────────────────────────────────────────
# REST ENDPOINTS
# ──────────────────────────────────────────────


@router.get("/rooms", response_model=list[ChatRoomResponse])
def list_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List chat rooms the current user belongs to."""
    rooms = (
        db.query(ChatRoom)
        .join(ChatMember)
        .filter(ChatMember.user_id == current_user.id)
        .all()
    )
    return rooms


@router.post("/rooms", response_model=ChatRoomResponse, status_code=201)
def create_room(
    body: ChatRoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a chat room and add members."""
    room = ChatRoom(
        name=body.name,
        is_group=body.is_group,
        created_by=current_user.id,
    )
    db.add(room)
    db.flush()

    # Add creator as member
    db.add(ChatMember(room_id=room.id, user_id=current_user.id))

    # Add other members
    for uid in body.member_ids:
        if uid != current_user.id:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                db.add(ChatMember(room_id=room.id, user_id=uid))

    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms/{room_id}", response_model=ChatRoomWithMembers)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get room details with members."""
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    membership = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    members = db.query(ChatMember).options(joinedload(ChatMember.user)).filter(ChatMember.room_id == room_id).all()

    return ChatRoomWithMembers(
        **ChatRoomResponse.model_validate(room).model_dump(),
        members=[UserResponse.model_validate(m.user) for m in members],
    )


@router.post("/rooms/{room_id}/join", status_code=200)
def join_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Join a room (for group chats)."""
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    existing = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == current_user.id)
        .first()
    )
    if existing:
        return {"message": "Already a member"}

    db.add(ChatMember(room_id=room_id, user_id=current_user.id))
    db.commit()
    return {"message": "Joined room"}


@router.get("/rooms/{room_id}/messages", response_model=list[ChatMessageWithUser])
def get_messages(
    room_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get message history for a room."""
    membership = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    messages = (
        db.query(ChatMessage)
        .options(joinedload(ChatMessage.user))
        .filter(ChatMessage.room_id == room_id)
        .order_by(ChatMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageResponse, status_code=201)
def send_message_rest(
    room_id: int,
    body: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message via REST (fallback when WebSocket unavailable)."""
    membership = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    msg = ChatMessage(
        room_id=room_id,
        user_id=current_user.id,
        content=body.content,
        message_type=body.message_type,
        is_offline=body.is_offline,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/rooms/{room_id}/sync", response_model=list[ChatMessageResponse])
def sync_offline_messages(
    room_id: int,
    body: ChatSyncPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync messages created offline when coming back online."""
    membership = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    created = []
    for m in body.messages:
        msg = ChatMessage(
            room_id=room_id,
            user_id=current_user.id,
            content=m.content,
            message_type=m.message_type,
            is_offline=True,
        )
        db.add(msg)
        db.flush()
        created.append(msg)

    db.commit()
    for m in created:
        db.refresh(m)
    return created


# ──────────────────────────────────────────────
# WEBSOCKET ENDPOINT
# ──────────────────────────────────────────────


@router.websocket("/ws/{room_id}")
async def websocket_chat(websocket: WebSocket, room_id: int, token: str = ""):
    """
    WebSocket endpoint for real-time chat.
    Connect: ws://host:port/api/v1/chat/ws/{room_id}?token=JWT

    Messages sent by client:
      {"content": "hello", "message_type": "text"}

    Messages broadcast to room:
      {"type": "message", "id": 1, "user_id": 2, "user_name": "Jane", "content": "hello", "created_at": "..."}
      {"type": "join", "user_id": 2, "user_name": "Jane"}
      {"type": "leave", "user_id": 2, "user_name": "Jane"}
      {"type": "online", "user_ids": [1, 2, 3]}
    """
    # Authenticate
    user = _authenticate_ws_token(token)
    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify membership
    db = SessionLocal()
    try:
        membership = (
            db.query(ChatMember)
            .filter(ChatMember.room_id == room_id, ChatMember.user_id == user.id)
            .first()
        )
        if not membership:
            await websocket.close(code=4003, reason="Not a member")
            return
    finally:
        db.close()

    await manager.connect(room_id, user.id, websocket)

    # Announce join
    await manager.broadcast(room_id, {
        "type": "join",
        "user_id": user.id,
        "user_name": user.full_name,
    })
    await manager.broadcast(room_id, {
        "type": "online",
        "user_ids": manager.get_online_users(room_id),
    })

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "").strip()
            message_type = data.get("message_type", "text")
            is_offline = data.get("is_offline", False)

            if not content:
                continue

            # Save to DB
            db = SessionLocal()
            try:
                msg = ChatMessage(
                    room_id=room_id,
                    user_id=user.id,
                    content=content,
                    message_type=message_type,
                    is_offline=is_offline,
                )
                db.add(msg)
                db.commit()
                db.refresh(msg)
                msg_id = msg.id
                msg_created = msg.created_at.isoformat()
            finally:
                db.close()

            # Broadcast to room
            await manager.broadcast(room_id, {
                "type": "message",
                "id": msg_id,
                "room_id": room_id,
                "user_id": user.id,
                "user_name": user.full_name,
                "content": content,
                "message_type": message_type,
                "is_offline": is_offline,
                "created_at": msg_created,
            })

    except WebSocketDisconnect:
        manager.disconnect(room_id, user.id)
        await manager.broadcast(room_id, {
            "type": "leave",
            "user_id": user.id,
            "user_name": user.full_name,
        })
        await manager.broadcast(room_id, {
            "type": "online",
            "user_ids": manager.get_online_users(room_id),
        })
