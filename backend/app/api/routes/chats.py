import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from starlette.websockets import WebSocketState

import app.models as models
from app.core.config import get_settings
from app.core.security import get_authenticated_user, get_authenticated_user_from_token
from app.database import get_session
from app.services.chat import ensure_project_group_chat
from app.services.upload_files import (
    build_s3_object_key,
    create_presigned_download_url,
    create_presigned_upload_url,
    delete_s3_object,
    get_s3_object_size,
    is_image_content_type,
    safe_file_name,
)

router = APIRouter()
settings = get_settings()
CHAT_ATTACHMENT_RETENTION_DAYS = 5
CHAT_ATTACHMENT_MESSAGE_TYPES = {"IMAGE", "FILE"}
CHAT_SESSION_REVALIDATE_SECONDS = 5
KST = timezone(timedelta(hours=9))


class CreateChatMessageRequest(BaseModel):
    content: str = ""
    message_type: str = "TEXT"
    uploaded_file_id: int | None = None


class UploadPrepareFileRequest(BaseModel):
    file_name: str
    content_type: str = "application/octet-stream"
    size_bytes: int


class UploadPrepareRequest(BaseModel):
    files: list[UploadPrepareFileRequest]


class ChatConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_users(self, user_ids: list[int], payload: dict[str, object]) -> None:
        stale_connections: list[tuple[int, WebSocket]] = []
        for user_id in user_ids:
            for websocket in list(self._connections.get(user_id, ())):
                try:
                    await websocket.send_json(payload)
                except Exception:
                    stale_connections.append((user_id, websocket))

        for user_id, websocket in stale_connections:
            self.disconnect(user_id, websocket)

    def send_to_users_threadsafe(self, user_ids: list[int], payload: dict[str, object]) -> None:
        if self._loop is None:
            return
        target_user_ids = [user_id for user_id in user_ids if self._connections.get(user_id)]
        if not target_user_ids:
            return
        asyncio.run_coroutine_threadsafe(self.send_to_users(target_user_ids, payload), self._loop)


chat_connection_manager = ChatConnectionManager()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=KST).isoformat()
    return value.astimezone(KST).isoformat()


def _is_websocket_not_connected_error(exc: RuntimeError) -> bool:
    return "WebSocket is not connected" in str(exc)


def _serialize_user(user: models.AppUser | None) -> dict[str, object] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "profile_image_url": user.profile_image_url,
    }


def _serialize_uploaded_file(
    uploaded_file: models.UploadedFile | None,
    expires_at: datetime | None,
) -> dict[str, object] | None:
    if uploaded_file is None:
        return None

    is_expired = bool(expires_at and expires_at <= datetime.now())
    is_image = is_image_content_type(uploaded_file.content_type)
    download_url: str | None = None
    preview_url: str | None = None
    if not is_expired:
        try:
            download_url = create_presigned_download_url(
                settings,
                object_key=uploaded_file.s3_object_key,
                file_name=uploaded_file.original_file_name,
                as_attachment=True,
            )
            if is_image:
                preview_url = create_presigned_download_url(
                    settings,
                    object_key=uploaded_file.s3_object_key,
                    file_name=uploaded_file.original_file_name,
                    as_attachment=False,
                )
        except Exception:
            download_url = None
            preview_url = None

    return {
        "id": uploaded_file.id,
        "file_name": uploaded_file.original_file_name,
        "content_type": uploaded_file.content_type,
        "file_size_bytes": uploaded_file.file_size_bytes,
        "is_image": is_image,
        "download_url": download_url,
        "preview_url": preview_url,
        "created_at": _iso(uploaded_file.created_at),
        "expires_at": _iso(expires_at),
        "is_expired": is_expired,
    }


def _get_unreferenced_uploaded_file(
    session: Session,
    uploaded_file: models.UploadedFile | None,
    current_message_id: int | None = None,
) -> models.UploadedFile | None:
    if uploaded_file is None:
        return None

    chat_query = session.query(func.count(models.ChatMessage.id)).filter(
        models.ChatMessage.uploaded_file_id == uploaded_file.id,
    )
    if current_message_id is not None:
        chat_query = chat_query.filter(models.ChatMessage.id != current_message_id)

    if int(chat_query.scalar() or 0) > 0:
        return None
    if int(session.query(func.count(models.WorkItemAttachment.id)).filter(models.WorkItemAttachment.uploaded_file_id == uploaded_file.id).scalar() or 0) > 0:
        return None
    if int(session.query(func.count(models.Evidence.id)).filter(models.Evidence.uploaded_file_id == uploaded_file.id).scalar() or 0) > 0:
        return None
    return uploaded_file


def _cleanup_expired_chat_attachments(session: Session, limit: int = 25) -> int:
    expired_messages = (
        session.query(models.ChatMessage)
        .options(joinedload(models.ChatMessage.uploaded_file))
        .filter(
            models.ChatMessage.uploaded_file_id.is_not(None),
            models.ChatMessage.attachment_expires_at.is_not(None),
            models.ChatMessage.attachment_expires_at <= datetime.now(),
        )
        .limit(limit)
        .all()
    )
    cleaned_count = 0
    for message in expired_messages:
        uploaded_file = message.uploaded_file
        message.uploaded_file_id = None
        session.flush()
        file_to_delete = _get_unreferenced_uploaded_file(session, uploaded_file, current_message_id=message.id)
        if file_to_delete is not None:
            try:
                delete_s3_object(settings, object_key=file_to_delete.s3_object_key)
            except Exception:
                pass
            session.delete(file_to_delete)
        cleaned_count += 1
    return cleaned_count


def cleanup_expired_chat_attachments_once(limit: int = 500) -> int:
    session = get_session()
    try:
        cleaned_count = _cleanup_expired_chat_attachments(session, limit=limit)
        session.commit()
        return cleaned_count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _count_message_unread_members(session: Session, message: models.ChatMessage) -> int:
    return int(
        session.query(func.count(models.ChatRoomMember.id))
        .filter(
            models.ChatRoomMember.room_id == message.room_id,
            models.ChatRoomMember.left_at.is_(None),
            models.ChatRoomMember.user_id != message.sender_user_id,
            models.ChatRoomMember.joined_at <= message.created_at,
            or_(
                models.ChatRoomMember.last_read_at.is_(None),
                models.ChatRoomMember.last_read_at < message.created_at,
            ),
        )
        .scalar()
        or 0
    )


def _serialize_message(session: Session, message: models.ChatMessage) -> dict[str, object]:
    return {
        "id": message.id,
        "room_id": message.room_id,
        "message_type": message.message_type,
        "content": message.content,
        "created_at": _iso(message.created_at),
        "attachment_expires_at": _iso(message.attachment_expires_at),
        "sender": _serialize_user(message.sender_user),
        "uploaded_file": _serialize_uploaded_file(message.uploaded_file, message.attachment_expires_at),
        "unread_count": _count_message_unread_members(session, message),
    }


def _serialize_message_unread_counts(
    session: Session,
    room_id: int,
    limit: int = 100,
) -> list[dict[str, int]]:
    messages = (
        session.query(models.ChatMessage)
        .filter(
            models.ChatMessage.room_id == room_id,
            models.ChatMessage.deleted_at.is_(None),
        )
        .order_by(models.ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "message_id": message.id,
            "unread_count": _count_message_unread_members(session, message),
        }
        for message in messages
    ]


def _get_active_room_user_ids(session: Session, room_id: int) -> list[int]:
    return [
        user_id
        for (user_id,) in session.query(models.ChatRoomMember.user_id)
        .filter(
            models.ChatRoomMember.room_id == room_id,
            models.ChatRoomMember.left_at.is_(None),
        )
        .all()
    ]


def _require_room_member(
    session: Session,
    room_id: int,
    user_id: int,
) -> tuple[models.ChatRoom, models.ChatRoomMember]:
    row = (
        session.query(models.ChatRoom, models.ChatRoomMember)
        .join(models.ChatRoomMember, models.ChatRoomMember.room_id == models.ChatRoom.id)
        .filter(
            models.ChatRoom.id == room_id,
            models.ChatRoomMember.user_id == user_id,
            models.ChatRoomMember.left_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Chat room not found.")
    return row


def _count_unread_messages(session: Session, room_member: models.ChatRoomMember, user_id: int) -> int:
    query = session.query(func.count(models.ChatMessage.id)).filter(
        models.ChatMessage.room_id == room_member.room_id,
        models.ChatMessage.sender_user_id != user_id,
        models.ChatMessage.deleted_at.is_(None),
    )
    if room_member.last_read_at is not None:
        query = query.filter(models.ChatMessage.created_at > room_member.last_read_at)
    else:
        query = query.filter(models.ChatMessage.created_at >= room_member.joined_at)
    return int(query.scalar() or 0)


def _serialize_room(
    session: Session,
    room: models.ChatRoom,
    room_member: models.ChatRoomMember,
    user_id: int,
) -> dict[str, object]:
    last_message = (
        session.query(models.ChatMessage)
        .options(joinedload(models.ChatMessage.sender_user), joinedload(models.ChatMessage.uploaded_file))
        .filter(
            models.ChatMessage.room_id == room.id,
            models.ChatMessage.deleted_at.is_(None),
        )
        .order_by(models.ChatMessage.id.desc())
        .first()
    )
    participants = (
        session.query(models.AppUser)
        .join(models.ChatRoomMember, models.ChatRoomMember.user_id == models.AppUser.id)
        .filter(
            models.ChatRoomMember.room_id == room.id,
            models.ChatRoomMember.left_at.is_(None),
        )
        .order_by(models.AppUser.name.asc())
        .all()
    )
    return {
        "id": room.id,
        "project": {
            "id": room.project.id,
            "title": room.project.title,
        },
        "room_type": room.room_type,
        "title": room.title or f"{room.project.title} 팀 채팅",
        "member_count": len(participants),
        "participants": [_serialize_user(user) for user in participants],
        "unread_count": _count_unread_messages(session, room_member, user_id),
        "last_message": _serialize_message(session, last_message) if last_message else None,
        "last_message_at": _iso(room.last_message_at),
        "updated_at": _iso(room.updated_at),
    }


def _sync_current_user_project_rooms(session: Session, user_id: int) -> None:
    projects = (
        session.query(models.Project)
        .join(models.ProjectMember, models.ProjectMember.project_id == models.Project.id)
        .filter(
            models.ProjectMember.user_id == user_id,
            models.ProjectMember.left_at.is_(None),
        )
        .all()
    )
    for project in projects:
        ensure_project_group_chat(session, project)


def _resolve_chat_uploaded_file(
    session: Session,
    *,
    room: models.ChatRoom,
    user_id: int,
    uploaded_file_id: int,
    message_type: str,
) -> models.UploadedFile:
    uploaded_file = (
        session.query(models.UploadedFile)
        .filter(
            models.UploadedFile.id == uploaded_file_id,
            models.UploadedFile.project_id == room.project_id,
            models.UploadedFile.uploaded_by_user_id == user_id,
        )
        .first()
    )
    if uploaded_file is None:
        raise HTTPException(status_code=400, detail="Uploaded file not found.")

    if message_type == "IMAGE" and not is_image_content_type(uploaded_file.content_type):
        raise HTTPException(status_code=400, detail="Only image files can be sent as image messages.")
    if message_type == "FILE" and is_image_content_type(uploaded_file.content_type):
        raise HTTPException(status_code=400, detail="Image files must be sent as image messages.")

    try:
        actual_size = get_s3_object_size(settings, object_key=uploaded_file.s3_object_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Uploaded file is not available: {uploaded_file.original_file_name}") from exc
    if actual_size != uploaded_file.file_size_bytes:
        raise HTTPException(status_code=400, detail=f"Uploaded file size does not match: {uploaded_file.original_file_name}")

    return uploaded_file


@router.get("/rooms", summary="List current user's chat rooms")
def list_chat_rooms(
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _sync_current_user_project_rooms(session, current_user.id)
        _cleanup_expired_chat_attachments(session)
        session.commit()

        rows = (
            session.query(models.ChatRoom, models.ChatRoomMember)
            .join(models.ChatRoomMember, models.ChatRoomMember.room_id == models.ChatRoom.id)
            .options(joinedload(models.ChatRoom.project))
            .filter(
                models.ChatRoomMember.user_id == current_user.id,
                models.ChatRoomMember.left_at.is_(None),
            )
            .order_by(models.ChatRoom.last_message_at.desc(), models.ChatRoom.created_at.desc())
            .all()
        )
        rooms = [_serialize_room(session, room, room_member, current_user.id) for room, room_member in rows]
        total_unread_count = sum(int(room["unread_count"]) for room in rooms)
        return {
            "current_user": _serialize_user(current_user),
            "rooms": rooms,
            "total_unread_count": total_unread_count,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.get("/rooms/{room_id}/messages", summary="List chat room messages")
def list_chat_messages(
    room_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
    before_id: int | None = None,
    limit: int = 50,
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        room, _room_member = _require_room_member(session, room_id, current_user.id)
        _cleanup_expired_chat_attachments(session)
        session.commit()
        safe_limit = min(max(limit, 1), 100)
        query = (
            session.query(models.ChatMessage)
            .options(joinedload(models.ChatMessage.sender_user), joinedload(models.ChatMessage.uploaded_file))
            .filter(
                models.ChatMessage.room_id == room.id,
                models.ChatMessage.deleted_at.is_(None),
            )
        )
        if before_id is not None:
            query = query.filter(models.ChatMessage.id < before_id)
        messages = query.order_by(models.ChatMessage.id.desc()).limit(safe_limit).all()
        messages.reverse()
        return {
            "room_id": room.id,
            "messages": [_serialize_message(session, message) for message in messages],
            "has_more": len(messages) == safe_limit,
        }
    finally:
        session.close()


@router.post("/rooms/{room_id}/uploads/presign", summary="Create chat attachment upload URLs")
def create_chat_upload_presigned_urls(
    room_id: int,
    payload: UploadPrepareRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        room, _room_member = _require_room_member(session, room_id, current_user.id)

        if not payload.files:
            raise HTTPException(status_code=400, detail="At least one file is required.")

        total_size = sum(file.size_bytes for file in payload.files)
        if total_size > settings.max_upload_total_bytes:
            raise HTTPException(status_code=400, detail="Total upload size cannot exceed 50MB.")

        items: list[dict[str, object]] = []
        for file in payload.files:
            file_name = safe_file_name(file.file_name)
            content_type = file.content_type.strip() or "application/octet-stream"
            if file.size_bytes <= 0:
                raise HTTPException(status_code=400, detail=f"Invalid file size: {file_name}")

            object_key = build_s3_object_key(room.project_id, file_name, f"{settings.s3_upload_prefix}/chat")
            upload_url = create_presigned_upload_url(
                settings,
                object_key=object_key,
                content_type=content_type,
            )
            uploaded_file = models.UploadedFile(
                project_id=room.project_id,
                uploaded_by_user_id=current_user.id,
                original_file_name=file_name,
                content_type=content_type,
                file_size_bytes=file.size_bytes,
                s3_bucket=settings.s3_bucket_name or "",
                s3_object_key=object_key,
            )
            session.add(uploaded_file)
            session.flush()

            items.append({
                "id": uploaded_file.id,
                "file_name": uploaded_file.original_file_name,
                "content_type": uploaded_file.content_type,
                "file_size_bytes": uploaded_file.file_size_bytes,
                "is_image": is_image_content_type(uploaded_file.content_type),
                "s3_object_key": uploaded_file.s3_object_key,
                "upload_url": upload_url,
                "retention_days": CHAT_ATTACHMENT_RETENTION_DAYS,
            })

        session.commit()
        return {
            "items": items,
            "max_total_bytes": settings.max_upload_total_bytes,
            "retention_days": CHAT_ATTACHMENT_RETENTION_DAYS,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.delete("/rooms/{room_id}/uploads/{file_id}", summary="Delete an unsent chat upload")
def delete_chat_uploaded_file(
    room_id: int,
    file_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        room, _room_member = _require_room_member(session, room_id, current_user.id)
        uploaded_file = (
            session.query(models.UploadedFile)
            .filter(
                models.UploadedFile.id == file_id,
                models.UploadedFile.project_id == room.project_id,
                models.UploadedFile.uploaded_by_user_id == current_user.id,
            )
            .first()
        )
        if uploaded_file is None:
            raise HTTPException(status_code=404, detail="Uploaded file not found.")
        if _get_unreferenced_uploaded_file(session, uploaded_file) is None:
            raise HTTPException(status_code=400, detail="Uploaded file is already linked.")

        object_key = uploaded_file.s3_object_key
        delete_s3_object(settings, object_key=object_key)
        session.delete(uploaded_file)
        session.commit()
        return {"message": "Uploaded file deleted.", "file_id": file_id}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/rooms/{room_id}/messages", summary="Create chat message", status_code=status.HTTP_201_CREATED)
def create_chat_message(
    room_id: int,
    payload: CreateChatMessageRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        room, room_member = _require_room_member(session, room_id, current_user.id)
        content = payload.content.strip()
        message_type = payload.message_type.upper().strip() or "TEXT"
        if message_type not in {"TEXT", "IMAGE", "FILE"}:
            raise HTTPException(status_code=400, detail="Unsupported chat message type.")
        if len(content) > 2000:
            raise HTTPException(status_code=400, detail="Message content cannot exceed 2000 characters.")

        uploaded_file: models.UploadedFile | None = None
        attachment_expires_at: datetime | None = None
        if message_type == "TEXT":
            if not content:
                raise HTTPException(status_code=400, detail="Message content is required.")
            if payload.uploaded_file_id is not None:
                raise HTTPException(status_code=400, detail="Text messages cannot include uploaded_file_id.")
        else:
            if payload.uploaded_file_id is None:
                raise HTTPException(status_code=400, detail="uploaded_file_id is required for attachment messages.")
            uploaded_file = _resolve_chat_uploaded_file(
                session,
                room=room,
                user_id=current_user.id,
                uploaded_file_id=payload.uploaded_file_id,
                message_type=message_type,
            )
            content = content or uploaded_file.original_file_name
            attachment_expires_at = datetime.now() + timedelta(days=CHAT_ATTACHMENT_RETENTION_DAYS)

        now = datetime.now()
        message = models.ChatMessage(
            room_id=room.id,
            sender_user_id=current_user.id,
            uploaded_file_id=uploaded_file.id if uploaded_file is not None else None,
            message_type=message_type,
            content=content,
            attachment_expires_at=attachment_expires_at,
            created_at=now,
        )
        room.last_message_at = now
        room.updated_at = now
        room_member.last_read_at = now
        session.add(message)
        session.flush()

        recipient_user_ids = _get_active_room_user_ids(session, room.id)
        session.commit()

        message = (
            session.query(models.ChatMessage)
            .options(joinedload(models.ChatMessage.sender_user), joinedload(models.ChatMessage.uploaded_file))
            .filter(models.ChatMessage.id == message.id)
            .one()
        )
        message_payload = _serialize_message(session, message)
        event_payload = {
            "type": "message_created",
            "room_id": room.id,
            "project_id": room.project_id,
            "message": message_payload,
        }
        chat_connection_manager.send_to_users_threadsafe(recipient_user_ids, event_payload)
        return {"message": message_payload}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/rooms/{room_id}/read", summary="Mark chat room as read")
def mark_chat_room_read(
    room_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        room, room_member = _require_room_member(session, room_id, current_user.id)
        room_member.last_read_at = datetime.now()
        session.flush()
        unread_counts = _serialize_message_unread_counts(session, room.id)
        recipient_user_ids = _get_active_room_user_ids(session, room.id)
        session.commit()
        chat_connection_manager.send_to_users_threadsafe(
            recipient_user_ids,
            {
                "type": "room_read_updated",
                "room_id": room.id,
                "project_id": room.project_id,
                "reader_user_id": current_user.id,
                "unread_counts": unread_counts,
            },
        )
        return {"room_id": room_id, "unread_count": 0, "unread_counts": unread_counts}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()



def _ensure_chat_session_is_active(access_token: str | None, expected_user_id: int) -> None:
    session = get_session()
    try:
        user = get_authenticated_user_from_token(session, access_token)
        if user.id != expected_user_id:
            raise HTTPException(status_code=401, detail="Session user changed.")
    finally:
        session.close()

@router.websocket("/ws")
async def chat_events(websocket: WebSocket) -> None:
    session = get_session()
    current_user_id: int | None = None
    try:
        access_token = websocket.cookies.get("access_token")
        if not access_token:
            authorization = websocket.headers.get("authorization")
            if authorization and authorization.startswith("Bearer "):
                access_token = authorization.removeprefix("Bearer ").strip()
        if not access_token:
            access_token = websocket.query_params.get("token")

        current_user = get_authenticated_user_from_token(session, access_token)
        current_user_id = current_user.id
        session.close()

        await chat_connection_manager.connect(current_user_id, websocket)
        if websocket.application_state != WebSocketState.CONNECTED:
            return
        await websocket.send_json({"type": "chat_connected", "occurred_at": datetime.now().isoformat()})

        while True:
            _ensure_chat_session_is_active(access_token, current_user_id)
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=CHAT_SESSION_REVALIDATE_SECONDS,
                )
            except asyncio.TimeoutError:
                continue
    except HTTPException as exc:
        close_code = 4401 if exc.status_code == 401 else 4403
        await websocket.close(code=close_code)
    except WebSocketDisconnect:
        pass
    except RuntimeError as exc:
        if not _is_websocket_not_connected_error(exc):
            raise
    finally:
        if current_user_id is not None:
            chat_connection_manager.disconnect(current_user_id, websocket)
        try:
            session.close()
        except Exception:
            pass
