import secrets
import string
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest, status
from pydantic import BaseModel
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

import app.models as models
from app.core.config import get_settings
from app.core.security import get_authenticated_user

router = APIRouter()
settings = get_settings()


class CreateProjectRequest(BaseModel):
    title: str
    description: str = ""
    start_date: date
    end_date: date
    join_policy: str = "LEADER_APPROVE"


class UpdateProjectRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    join_policy: str | None = None
    join_code_active: bool | None = None
    join_code_expires_at: datetime | None = None


class UpdateProjectMemberRequest(BaseModel):
    project_role: str | None = None
    position_label: str | None = None
    memo: str | None = None


class ReviewProjectJoinRequest(BaseModel):
    request_status: str
    reviewed_project_role: str | None = None
    reviewed_position_label: str | None = None
    review_note: str | None = None


def get_engine():
    return create_engine(settings.database_url)


def get_session() -> Session:
    session_factory = sessionmaker(bind=get_engine())
    return session_factory()


def _serialize_current_user(user: models.AppUser) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "department": user.department,
        "profile_image_url": user.profile_image_url,
        "status": user.status,
    }


def _serialize_project_membership(project_member: models.ProjectMember) -> dict[str, object]:
    return {
        "project_member_id": project_member.id,
        "project_role": project_member.project_role,
        "position_label": project_member.position_label,
        "joined_at": project_member.joined_at.isoformat(),
        "left_at": project_member.left_at.isoformat() if project_member.left_at else None,
    }


def _serialize_project_summary(
    project: models.Project,
    project_member: models.ProjectMember,
    member_count: int,
) -> dict[str, object]:
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "status": project.status,
        "start_date": project.start_date.isoformat(),
        "end_date": project.end_date.isoformat(),
        "join_policy": project.join_policy,
        "join_code_active": project.join_code_active,
        "join_code_expires_at": project.join_code_expires_at.isoformat()
        if project.join_code_expires_at
        else None,
        "member_count": member_count,
        "my_membership": _serialize_project_membership(project_member),
    }


def _get_member_count(session: Session, project_id: int) -> int:
    member_count = (
        session.query(func.count(models.ProjectMember.id))
        .filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.left_at.is_(None),
        )
        .scalar()
    )
    return int(member_count or 0)


def _generate_join_code(session: Session, length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = (
            session.query(models.Project.id)
            .filter(models.Project.join_code == candidate)
            .first()
        )
        if exists is None:
            return candidate

    raise HTTPException(status_code=500, detail="Failed to generate a unique join code.")


@router.get("", summary="List projects for current user")
def list_projects(
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)

        active_member_count_subquery = (
            session.query(
                models.ProjectMember.project_id.label("project_id"),
                func.count(models.ProjectMember.id).label("member_count"),
            )
            .filter(models.ProjectMember.left_at.is_(None))
            .group_by(models.ProjectMember.project_id)
            .subquery()
        )

        rows = (
            session.query(
                models.Project,
                models.ProjectMember,
                active_member_count_subquery.c.member_count,
            )
            .join(
                models.ProjectMember,
                (models.ProjectMember.project_id == models.Project.id)
                & (models.ProjectMember.user_id == current_user.id)
                & (models.ProjectMember.left_at.is_(None)),
            )
            .outerjoin(
                active_member_count_subquery,
                active_member_count_subquery.c.project_id == models.Project.id,
            )
            .order_by(models.Project.created_at.desc())
            .all()
        )

        projects = [
            _serialize_project_summary(project, project_member, int(member_count or 0))
            for project, project_member, member_count in rows
        ]

        return {
            "authenticated": True,
            "user": _serialize_current_user(current_user),
            "current_user": _serialize_current_user(current_user),
            "projects": projects,
            "count": len(projects),
        }
    finally:
        session.close()


@router.post("", summary="Create project", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: CreateProjectRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)

        title = payload.title.strip()
        description = payload.description.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Project title is required.")
        if payload.end_date < payload.start_date:
            raise HTTPException(status_code=400, detail="Project end date cannot be earlier than the start date.")

        now = datetime.now()
        project = models.Project(
            title=title,
            description=description,
            created_by_user_id=current_user.id,
            join_code=_generate_join_code(session),
            join_code_active=True,
            join_policy=payload.join_policy,
            join_code_created_at=now,
            join_code_expires_at=now + timedelta(days=14),
            start_date=payload.start_date,
            end_date=payload.end_date,
            status="PLANNING",
        )
        session.add(project)
        session.flush()

        leader_member = models.ProjectMember(
            project_id=project.id,
            user_id=current_user.id,
            project_role="LEADER",
            position_label="Team Lead",
            memo="Project creator",
        )
        session.add(leader_member)
        session.commit()
        session.refresh(project)
        session.refresh(leader_member)

        return {
            "message": "Project created.",
            "project": _serialize_project_summary(project, leader_member, 1),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.get("/{project_id}", summary="Get project detail")
def get_project(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)

        project = session.query(models.Project).filter(models.Project.id == project_id).first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")

        my_membership = (
            session.query(models.ProjectMember)
            .filter(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.user_id == current_user.id,
                models.ProjectMember.left_at.is_(None),
            )
            .first()
        )
        if my_membership is None:
            raise HTTPException(status_code=403, detail="Only active project members can access this project.")

        active_members = (
            session.query(models.ProjectMember, models.AppUser)
            .join(models.AppUser, models.AppUser.id == models.ProjectMember.user_id)
            .filter(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.left_at.is_(None),
            )
            .all()
        )
        sorted_members = sorted(
            active_members,
            key=lambda row: (row[0].project_role != "LEADER", row[1].name.casefold()),
        )
        member_count = len(sorted_members)

        work_items = (
            session.query(models.WorkItem)
            .filter(models.WorkItem.project_id == project_id)
            .order_by(models.WorkItem.created_at.asc())
            .all()
        )
        total_work_items = len(work_items)
        todo_count = sum(1 for work_item in work_items if work_item.status == "TODO")
        in_progress_count = sum(1 for work_item in work_items if work_item.status == "IN_PROGRESS")
        done_count = sum(1 for work_item in work_items if work_item.status == "DONE")
        completion_rate = int((done_count / total_work_items) * 100) if total_work_items else 0

        recent_activities = (
            session.query(models.Activity, models.AppUser, models.WorkItem)
            .join(models.AppUser, models.AppUser.id == models.Activity.actor_user_id)
            .outerjoin(models.WorkItem, models.WorkItem.id == models.Activity.work_item_id)
            .filter(models.Activity.project_id == project_id)
            .order_by(models.Activity.occurred_at.desc())
            .limit(5)
            .all()
        )

        return {
            "authenticated": True,
            "current_user": _serialize_current_user(current_user),
            "project": {
                "id": project.id,
                "title": project.title,
                "description": project.description,
                "status": project.status,
                "start_date": project.start_date.isoformat(),
                "end_date": project.end_date.isoformat(),
                "join_policy": project.join_policy,
                "join_code": project.join_code,
                "join_code_active": project.join_code_active,
                "join_code_expires_at": project.join_code_expires_at.isoformat()
                if project.join_code_expires_at
                else None,
                "member_count": member_count,
                "my_membership": _serialize_project_membership(my_membership),
                "members": [
                    {
                        "project_member_id": project_member.id,
                        "user_id": member.id,
                        "name": member.name,
                        "email": member.email,
                        "project_role": project_member.project_role,
                        "position_label": project_member.position_label,
                    }
                    for project_member, member in sorted_members
                ],
                "overview": {
                    "total_work_items": total_work_items,
                    "todo_work_items": todo_count,
                    "in_progress_work_items": in_progress_count,
                    "done_work_items": done_count,
                    "completion_rate": completion_rate,
                    "recent_activities": [
                        {
                            "id": activity.id,
                            "title": activity.title,
                            "content": activity.content,
                            "activity_type": activity.activity_type,
                            "review_state": activity.review_state,
                            "occurred_at": activity.occurred_at.isoformat(),
                            "actor": {
                                "id": actor.id,
                                "name": actor.name,
                            },
                            "work_item": {
                                "id": work_item.id,
                                "title": work_item.title,
                            }
                            if work_item
                            else None,
                        }
                        for activity, actor, work_item in recent_activities
                    ],
                },
            },
        }
    finally:
        session.close()


@router.patch("/{project_id}", summary="Update project")
def update_project(project_id: int, payload: UpdateProjectRequest) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "PATCH /api/projects/{project_id} will update project metadata.",
        "project_id": project_id,
        "payload": payload.model_dump(exclude_none=True),
    }


@router.get("/join-preview/{join_code}", summary="Preview project by join code")
def preview_project_by_join_code(
    join_code: str,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        normalized_join_code = join_code.strip().upper()
        project = (
            session.query(models.Project)
            .filter(
                models.Project.join_code == normalized_join_code,
                models.Project.join_code_active.is_(True),
            )
            .first()
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Join code not found.")

        if project.join_code_expires_at and project.join_code_expires_at < datetime.now():
            raise HTTPException(status_code=410, detail="Join code has expired.")

        active_membership = (
            session.query(models.ProjectMember)
            .filter(
                models.ProjectMember.project_id == project.id,
                models.ProjectMember.user_id == current_user.id,
                models.ProjectMember.left_at.is_(None),
            )
            .first()
        )

        return {
            "project": {
                "id": project.id,
                "title": project.title,
                "description": project.description,
                "status": project.status,
                "start_date": project.start_date.isoformat(),
                "end_date": project.end_date.isoformat(),
                "join_policy": project.join_policy,
                "member_count": _get_member_count(session, project.id),
            },
            "already_member": active_membership is not None,
        }
    finally:
        session.close()


@router.post("/{project_id}/join-code/regenerate", summary="Regenerate join code")
def regenerate_join_code(project_id: int) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "POST /api/projects/{project_id}/join-code/regenerate will issue a new join code.",
        "project_id": project_id,
    }


@router.get("/{project_id}/members", summary="List project members")
def list_project_members(project_id: int) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "GET /api/projects/{project_id}/members will list project members.",
        "project_id": project_id,
    }


@router.patch("/{project_id}/members/{member_id}", summary="Update project member")
def update_project_member(
    project_id: int,
    member_id: int,
    payload: UpdateProjectMemberRequest,
) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "PATCH /api/projects/{project_id}/members/{member_id} will update member role and position.",
        "project_id": project_id,
        "member_id": member_id,
        "payload": payload.model_dump(exclude_none=True),
    }


@router.delete("/{project_id}/members/{member_id}", summary="Leave or remove project member")
def remove_project_member(project_id: int, member_id: int) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "DELETE /api/projects/{project_id}/members/{member_id} will set left_at instead of hard delete.",
        "project_id": project_id,
        "member_id": member_id,
    }


@router.get("/{project_id}/join-requests", summary="List project join requests")
def list_project_join_requests(project_id: int) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "GET /api/projects/{project_id}/join-requests will list pending join requests for the leader.",
        "project_id": project_id,
    }


@router.patch("/{project_id}/join-requests/{request_id}", summary="Review project join request")
def review_project_join_request(
    project_id: int,
    request_id: int,
    payload: ReviewProjectJoinRequest,
) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "PATCH /api/projects/{project_id}/join-requests/{request_id} will approve or reject a join request.",
        "project_id": project_id,
        "request_id": request_id,
        "payload": payload.model_dump(exclude_none=True),
    }
