import asyncio
import secrets
import string
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

import app.models as models
from app.core.config import get_settings
from app.core.security import get_authenticated_user, get_authenticated_user_from_token
from app.database import get_session

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


class CreateWorkItemRequest(BaseModel):
    title: str
    description: str = ""
    status: str = "TODO"
    priority: str = "MEDIUM"
    assignee_user_id: int | None = None
    timeline_start_date: date
    timeline_end_date: date


class UpdateWorkItemRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee_user_id: int | None = None
    timeline_start_date: date | None = None
    timeline_end_date: date | None = None


class CreateWorkItemDependencyRequest(BaseModel):
    predecessor_work_item_id: int
    successor_work_item_id: int
class ProjectWorkItemConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, project_id: int, websocket: WebSocket) -> None:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        await websocket.accept()
        self._connections[project_id].add(websocket)

    def disconnect(self, project_id: int, websocket: WebSocket) -> None:
        connections = self._connections.get(project_id)
        if not connections:
            return

        connections.discard(websocket)
        if not connections:
            self._connections.pop(project_id, None)

    async def broadcast(self, project_id: int, payload: dict[str, object]) -> None:
        connections = list(self._connections.get(project_id, ()))
        stale_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(project_id, websocket)

    def broadcast_threadsafe(self, project_id: int, payload: dict[str, object]) -> None:
        if self._loop is None or not self._connections.get(project_id):
            return

        asyncio.run_coroutine_threadsafe(self.broadcast(project_id, payload), self._loop)


work_item_connection_manager = ProjectWorkItemConnectionManager()


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


def _get_work_item_timeline_dates(work_item: models.WorkItem) -> tuple[date, date]:
    timeline_start = work_item.started_at.date() if work_item.started_at else work_item.created_at.date()
    timeline_end = (
        work_item.completed_at.date()
        if work_item.completed_at
        else work_item.due_date or timeline_start
    )

    if timeline_end < timeline_start:
        timeline_end = timeline_start

    return timeline_start, timeline_end


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


def _get_active_project_membership(
    session: Session,
    project_id: int,
    user_id: int,
) -> models.ProjectMember | None:
    return (
        session.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.user_id == user_id,
            models.ProjectMember.left_at.is_(None),
        )
        .first()
    )


def _require_project_access(
    session: Session,
    project_id: int,
    user_id: int,
) -> tuple[models.Project, models.ProjectMember]:
    project = session.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    membership = _get_active_project_membership(session, project_id, user_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Only active project members can access this project.")

    return project, membership


def _serialize_work_item_dependency(
    dependency: models.WorkItemDependency,
) -> dict[str, object]:
    return {
        "id": dependency.id,
        "predecessor_work_item_id": dependency.predecessor_work_item_id,
        "successor_work_item_id": dependency.successor_work_item_id,
        "created_at": dependency.created_at.isoformat(),
    }


def _serialize_project_work_item(work_item: models.WorkItem) -> dict[str, object]:
    creator = work_item.creator_user
    assignee = work_item.assignee_user
    timeline_start, timeline_end = _get_work_item_timeline_dates(work_item)
    duration_days = (timeline_end - timeline_start).days + 1

    return {
        "id": work_item.id,
        "title": work_item.title,
        "description": work_item.description,
        "status": work_item.status,
        "priority": work_item.priority,
        "due_date": work_item.due_date.isoformat() if work_item.due_date else None,
        "started_at": work_item.started_at.isoformat() if work_item.started_at else None,
        "completed_at": work_item.completed_at.isoformat() if work_item.completed_at else None,
        "created_at": work_item.created_at.isoformat(),
        "updated_at": work_item.updated_at.isoformat(),
        "timeline_start_date": timeline_start.isoformat(),
        "timeline_end_date": timeline_end.isoformat(),
        "duration_days": duration_days,
        "creator": {
            "id": creator.id,
            "name": creator.name,
        },
        "assignee": {
            "id": assignee.id,
            "name": assignee.name,
        }
        if assignee
        else None,
    }


def _build_project_work_item_snapshot(
    session: Session,
    project_id: int,
) -> dict[str, object]:
    work_items = (
        session.query(models.WorkItem)
        .filter(models.WorkItem.project_id == project_id)
        .order_by(models.WorkItem.created_at.asc(), models.WorkItem.id.asc())
        .all()
    )
    dependencies = (
        session.query(models.WorkItemDependency)
        .filter(models.WorkItemDependency.project_id == project_id)
        .order_by(models.WorkItemDependency.created_at.asc(), models.WorkItemDependency.id.asc())
        .all()
    )

    return {
        "project_id": project_id,
        "count": len(work_items),
        "items": [_serialize_project_work_item(work_item) for work_item in work_items],
        "dependency_count": len(dependencies),
        "dependencies": [
            _serialize_work_item_dependency(dependency)
            for dependency in dependencies
        ],
    }


def _validate_work_item_status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"TODO", "IN_PROGRESS", "DONE"}:
        raise HTTPException(status_code=400, detail="Unsupported work item status.")
    return normalized


def _validate_work_item_priority(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"LOW", "MEDIUM", "HIGH"}:
        raise HTTPException(status_code=400, detail="Unsupported work item priority.")
    return normalized


def _combine_work_date(value: date, *, end_of_day: bool = False) -> datetime:
    if end_of_day:
        return datetime.combine(value, time(hour=18))
    return datetime.combine(value, time(hour=9))


def _apply_work_item_schedule(
    work_item: models.WorkItem,
    timeline_start_date: date,
    timeline_end_date: date,
    *,
    status: str,
) -> None:
    if timeline_end_date < timeline_start_date:
        raise HTTPException(status_code=400, detail="Work item end date cannot be earlier than the start date.")
    if timeline_start_date < work_item.created_at.date():
        raise HTTPException(
            status_code=400,
            detail="Work item start date cannot be earlier than the creation date in the current schema.",
        )

    work_item.started_at = _combine_work_date(timeline_start_date)
    work_item.due_date = timeline_end_date
    work_item.completed_at = (
        _combine_work_date(timeline_end_date, end_of_day=True)
        if status == "DONE"
        else None
    )


def _ensure_assignable_member(
    session: Session,
    project_id: int,
    assignee_user_id: int | None,
) -> int | None:
    if assignee_user_id is None:
        return None

    membership = _get_active_project_membership(session, project_id, assignee_user_id)
    if membership is None:
        raise HTTPException(status_code=400, detail="Assignee must be an active project member.")
    return assignee_user_id


def _require_project_work_item(
    session: Session,
    project_id: int,
    work_item_id: int,
) -> models.WorkItem:
    work_item = (
        session.query(models.WorkItem)
        .filter(
            models.WorkItem.project_id == project_id,
            models.WorkItem.id == work_item_id,
        )
        .first()
    )
    if work_item is None:
        raise HTTPException(status_code=404, detail="Work item not found.")
    return work_item


def _require_project_work_item_dependency(
    session: Session,
    project_id: int,
    dependency_id: int,
) -> models.WorkItemDependency:
    dependency = (
        session.query(models.WorkItemDependency)
        .filter(
            models.WorkItemDependency.project_id == project_id,
            models.WorkItemDependency.id == dependency_id,
        )
        .first()
    )
    if dependency is None:
        raise HTTPException(status_code=404, detail="Work item dependency not found.")
    return dependency


def _ensure_same_project_work_item_pair(
    session: Session,
    project_id: int,
    predecessor_work_item_id: int,
    successor_work_item_id: int,
) -> tuple[models.WorkItem, models.WorkItem]:
    predecessor = _require_project_work_item(session, project_id, predecessor_work_item_id)
    successor = _require_project_work_item(session, project_id, successor_work_item_id)
    if predecessor.id == successor.id:
        raise HTTPException(status_code=400, detail="A work item cannot depend on itself.")
    return predecessor, successor


def _broadcast_project_work_item_change(
    project_id: int,
    change_type: str,
    resource_id: int | None = None,
) -> None:
    payload: dict[str, object] = {
        "type": "work_items_changed",
        "change_type": change_type,
        "project_id": project_id,
        "occurred_at": datetime.now().isoformat(),
    }
    if resource_id is not None:
        payload["resource_id"] = resource_id

    work_item_connection_manager.broadcast_threadsafe(project_id, payload)


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


@router.get("/{project_id}/work-items", summary="List project work items")
def list_project_work_items(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        project, _membership = _require_project_access(session, project_id, current_user.id)
        return _build_project_work_item_snapshot(session, project.id)
    finally:
        session.close()


@router.post(
    "/{project_id}/work-items",
    summary="Create project work item",
    status_code=status.HTTP_201_CREATED,
)
def create_project_work_item(
    project_id: int,
    payload: CreateWorkItemRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        project, _membership = _require_project_access(session, project_id, current_user.id)

        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Work item title is required.")

        status_value = _validate_work_item_status(payload.status)
        priority_value = _validate_work_item_priority(payload.priority)
        assignee_user_id = _ensure_assignable_member(session, project_id, payload.assignee_user_id)
        now = datetime.now()

        work_item = models.WorkItem(
            project_id=project.id,
            creator_user_id=current_user.id,
            assignee_user_id=assignee_user_id,
            title=title,
            description=payload.description.strip(),
            status=status_value,
            priority=priority_value,
            created_at=now,
            updated_at=now,
        )
        session.add(work_item)
        session.flush()
        _apply_work_item_schedule(
            work_item,
            payload.timeline_start_date,
            payload.timeline_end_date,
            status=status_value,
        )
        session.commit()
        session.refresh(work_item)

        _broadcast_project_work_item_change(project.id, "work_item_created", work_item.id)
        return {
            "message": "Work item created.",
            "item": _serialize_project_work_item(work_item),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.patch("/{project_id}/work-items/{work_item_id}", summary="Update project work item")
def update_project_work_item(
    project_id: int,
    work_item_id: int,
    payload: UpdateWorkItemRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, current_user.id)
        work_item = _require_project_work_item(session, project_id, work_item_id)
        changed_fields = payload.model_fields_set

        if "title" in changed_fields and payload.title is not None:
            title = payload.title.strip()
            if not title:
                raise HTTPException(status_code=400, detail="Work item title is required.")
            work_item.title = title

        if "description" in changed_fields and payload.description is not None:
            work_item.description = payload.description.strip()

        status_value = work_item.status
        if "status" in changed_fields and payload.status is not None:
            status_value = _validate_work_item_status(payload.status)
            work_item.status = status_value

        if "priority" in changed_fields and payload.priority is not None:
            work_item.priority = _validate_work_item_priority(payload.priority)

        if "assignee_user_id" in changed_fields:
            work_item.assignee_user_id = _ensure_assignable_member(
                session,
                project_id,
                payload.assignee_user_id,
            )

        current_timeline_start, current_timeline_end = _get_work_item_timeline_dates(work_item)
        next_timeline_start = payload.timeline_start_date or current_timeline_start
        next_timeline_end = payload.timeline_end_date or current_timeline_end
        _apply_work_item_schedule(
            work_item,
            next_timeline_start,
            next_timeline_end,
            status=status_value,
        )
        work_item.updated_at = datetime.now()

        session.commit()
        session.refresh(work_item)

        _broadcast_project_work_item_change(project_id, "work_item_updated", work_item.id)
        return {
            "message": "Work item updated.",
            "item": _serialize_project_work_item(work_item),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.delete("/{project_id}/work-items/{work_item_id}", summary="Delete project work item")
def delete_project_work_item(
    project_id: int,
    work_item_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, current_user.id)
        work_item = _require_project_work_item(session, project_id, work_item_id)

        session.delete(work_item)
        session.commit()

        _broadcast_project_work_item_change(project_id, "work_item_deleted", work_item_id)
        return {
            "message": "Work item deleted.",
            "work_item_id": work_item_id,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post(
    "/{project_id}/work-item-dependencies",
    summary="Create project work item dependency",
    status_code=status.HTTP_201_CREATED,
)
def create_project_work_item_dependency(
    project_id: int,
    payload: CreateWorkItemDependencyRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, current_user.id)
        predecessor, successor = _ensure_same_project_work_item_pair(
            session,
            project_id,
            payload.predecessor_work_item_id,
            payload.successor_work_item_id,
        )

        existing_dependency = (
            session.query(models.WorkItemDependency)
            .filter(
                models.WorkItemDependency.project_id == project_id,
                models.WorkItemDependency.predecessor_work_item_id == predecessor.id,
                models.WorkItemDependency.successor_work_item_id == successor.id,
            )
            .first()
        )
        if existing_dependency is not None:
            raise HTTPException(status_code=409, detail="This dependency already exists.")

        dependency = models.WorkItemDependency(
            project_id=project_id,
            predecessor_work_item_id=predecessor.id,
            successor_work_item_id=successor.id,
        )
        session.add(dependency)
        session.commit()
        session.refresh(dependency)

        _broadcast_project_work_item_change(project_id, "dependency_created", dependency.id)
        return {
            "message": "Work item dependency created.",
            "dependency": _serialize_work_item_dependency(dependency),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.delete(
    "/{project_id}/work-item-dependencies/{dependency_id}",
    summary="Delete project work item dependency",
)
def delete_project_work_item_dependency(
    project_id: int,
    dependency_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, current_user.id)
        dependency = _require_project_work_item_dependency(session, project_id, dependency_id)

        session.delete(dependency)
        session.commit()

        _broadcast_project_work_item_change(project_id, "dependency_deleted", dependency_id)
        return {
            "message": "Work item dependency deleted.",
            "dependency_id": dependency_id,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.websocket("/{project_id}/work-items/ws")
async def project_work_item_events(
    websocket: WebSocket,
    project_id: int,
) -> None:
    session = get_session()
    try:
        access_token = websocket.cookies.get("access_token")
        if not access_token:
            authorization = websocket.headers.get("authorization")
            if authorization and authorization.startswith("Bearer "):
                access_token = authorization.removeprefix("Bearer ").strip()
        if not access_token:
            access_token = websocket.query_params.get("token")

        current_user = get_authenticated_user_from_token(session, access_token)
        _require_project_access(session, project_id, current_user.id)

        await work_item_connection_manager.connect(project_id, websocket)
        await websocket.send_json(
            {
                "type": "work_items_connected",
                "project_id": project_id,
                "occurred_at": datetime.now().isoformat(),
            }
        )

        while True:
            await websocket.receive_text()
    except HTTPException as exc:
        close_code = 4401 if exc.status_code == 401 else 4403
        await websocket.close(code=close_code)
    except WebSocketDisconnect:
        pass
    finally:
        work_item_connection_manager.disconnect(project_id, websocket)
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

        my_membership = _get_active_project_membership(session, project_id, current_user.id)
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
