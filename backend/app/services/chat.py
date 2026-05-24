from datetime import datetime

from sqlalchemy.orm import Session

import app.models as models

DEFAULT_PROJECT_ROOM_KEY = "PROJECT_DEFAULT"


def ensure_project_group_chat(
    session: Session,
    project: models.Project,
    created_by_user_id: int | None = None,
) -> models.ChatRoom:
    room = (
        session.query(models.ChatRoom)
        .filter(
            models.ChatRoom.project_id == project.id,
            models.ChatRoom.room_key == DEFAULT_PROJECT_ROOM_KEY,
        )
        .first()
    )
    if room is None:
        room = models.ChatRoom(
            project_id=project.id,
            room_type="GROUP",
            room_key=DEFAULT_PROJECT_ROOM_KEY,
            title=f"{project.title} 팀 채팅",
            created_by_user_id=created_by_user_id or project.created_by_user_id,
        )
        session.add(room)
        session.flush()

    sync_project_group_chat_members(session, room)
    return room


def sync_project_group_chat_members(session: Session, room: models.ChatRoom) -> None:
    now = datetime.now()
    active_members = (
        session.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == room.project_id,
            models.ProjectMember.left_at.is_(None),
        )
        .all()
    )
    active_user_ids = {member.user_id for member in active_members}

    room_members = (
        session.query(models.ChatRoomMember)
        .filter(models.ChatRoomMember.room_id == room.id)
        .all()
    )
    room_member_by_user_id = {member.user_id: member for member in room_members}

    for project_member in active_members:
        room_member = room_member_by_user_id.get(project_member.user_id)
        if room_member is None:
            session.add(
                models.ChatRoomMember(
                    room_id=room.id,
                    user_id=project_member.user_id,
                    joined_at=project_member.joined_at,
                )
            )
        elif room_member.left_at is not None:
            room_member.left_at = None

    for room_member in room_members:
        if room_member.user_id not in active_user_ids and room_member.left_at is None:
            room_member.left_at = now
