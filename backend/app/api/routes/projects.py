import asyncio
import secrets
import string
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased, selectinload, joinedload

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
    status: str = "PLANNING"


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
    parent_work_item_id: int | None = None
    gantt_sort_order: int | None = None
    timeline_start_date: date
    timeline_end_date: date


class UpdateWorkItemRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee_user_id: int | None = None
    parent_work_item_id: int | None = None
    gantt_sort_order: int | None = None
    timeline_start_date: date | None = None
    timeline_end_date: date | None = None


class CreateWorkItemDependencyRequest(BaseModel):
    predecessor_work_item_id: int
    successor_work_item_id: int


class WorkItemHierarchyEntryRequest(BaseModel):
    work_item_id: int
    parent_work_item_id: int | None = None
    gantt_sort_order: int


class UpdateWorkItemHierarchyRequest(BaseModel):
    items: list[WorkItemHierarchyEntryRequest]

class EvidenceCreateRequest(BaseModel):
    evidence_type: str
    evidence_role: str = "SUPPORTING"
    description: str | None = None
    resource_url: str | None = None
    file_name: str | None = None

class ActivityCreateRequest(BaseModel):
    work_item_ids: list[int] = []
    target_task_status: str | None = None
    category: str = "BASIC"
    activity_type: str = "FINALIZATION"
    contribution_phase: str = "FINALIZATION"
    title: str
    content: str
    target_user_id: int | None = None
    evidences: list[EvidenceCreateRequest] = []


class EvidenceCreateRequest(BaseModel):
    evidence_type: str
    evidence_role: str = "SUPPORTING"
    description: str | None = None
    resource_url: str | None = None
    file_name: str | None = None

class ActivityCreateRequest(BaseModel):
    work_item_ids: list[int] = []
    target_task_status: str | None = None
    category: str = "BASIC"
    activity_type: str = "FINALIZATION"
    contribution_phase: str = "FINALIZATION"
    title: str
    content: str
    target_user_id: int | None = None
    evidences: list[EvidenceCreateRequest] = []

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


class ProjectPresenceManager:
    def __init__(self) -> None:
        self._active_users = __import__("collections").defaultdict(dict)
        self._connections = __import__("collections").defaultdict(dict)

    async def connect(self, project_id: int, user_summary: dict, websocket: WebSocket) -> None:
        await websocket.accept()
        user_id = user_summary["id"]
        self._connections[project_id][websocket] = user_id
        
        if user_id not in self._active_users[project_id]:
           self._active_users[project_id][user_id] = {"count": 1, "info": user_summary}
        else:
           self._active_users[project_id][user_id]["count"] += 1
           
        await self.broadcast_presence(project_id)

    async def disconnect(self, project_id: int, websocket: WebSocket) -> None:
        user_id = self._connections.get(project_id, {}).pop(websocket, None)
        if user_id and user_id in self._active_users.get(project_id, {}):
            self._active_users[project_id][user_id]["count"] -= 1
            if self._active_users[project_id][user_id]["count"] <= 0:
                del self._active_users[project_id][user_id]
            await self.broadcast_presence(project_id)

    async def broadcast_presence(self, project_id: int) -> None:
        users = [data["info"] for data in self._active_users.get(project_id, {}).values()]
        payload = {"type": "presence_update", "active_users": users}
        stale_connections = []
        for ws in list(self._connections.get(project_id, {}).keys()):
            try:
                await ws.send_json(payload)
            except Exception:
                stale_connections.append(ws)
        
        for ws in stale_connections:
            await self.disconnect(project_id, ws)

presence_manager = ProjectPresenceManager()




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


def _serialize_activity(activity: models.Activity) -> dict[str, object]:
    actor = activity.actor_user
    target_user = activity.target_user
    return {
        "id": activity.id,
        "title": activity.title,
        "content": activity.content,
        "activity_category": activity.activity_category,
        "activity_type": activity.activity_type,
        "contribution_phase": activity.contribution_phase,
        "review_state": activity.review_state,
        "credibility_level": activity.credibility_level,
        "source_type": activity.source_type,
        "version": activity.version,
        "occurred_at": activity.occurred_at.isoformat(),
        "created_at": activity.created_at.isoformat(),
        "updated_at": activity.updated_at.isoformat(),
        "is_modified": activity.updated_at > activity.occurred_at,
        "actor": {
            "id": actor.id,
            "name": actor.name,
            "profile_image_url": actor.profile_image_url,
        }
        if actor
        else None,
        "target_user": {
            "id": target_user.id,
            "name": target_user.name,
            "profile_image_url": target_user.profile_image_url,
        }
        if target_user
        else None,
        "work_items": [
            {
                "id": work_item.id,
                "title": work_item.title,
                "description": work_item.description,
                "status": work_item.status,
                "assignee": {
                    "id": work_item.assignee_user.id,
                    "name": work_item.assignee_user.name,
                    "profile_image_url": work_item.assignee_user.profile_image_url,
                }
                if work_item.assignee_user
                else None,
                "timeline_start_date": _get_work_item_timeline_dates(work_item)[0].isoformat(),
                "timeline_end_date": _get_work_item_timeline_dates(work_item)[1].isoformat(),
            }
            for work_item in activity.work_items
        ],
        "evidences": [
            {
                "id": evidence.id,
                "evidence_type": evidence.evidence_type,
                "evidence_role": evidence.evidence_role,
                "file_name": evidence.file_name,
                "description": evidence.description,
                "resource_url": evidence.resource_url,
                "verification_status": evidence.verification_status,
                "created_at": evidence.created_at.isoformat(),
            }
            for evidence in getattr(activity, "evidence_items", [])
        ],
        "reactions": [
            {
                "reactor_user_id": reaction.reactor_user_id,
                "reaction_type": reaction.reaction_type,
                "created_at": reaction.created_at.isoformat(),
            }
            for reaction in getattr(activity, "reactions", [])
        ],
    }


def _serialize_project_work_item(work_item: models.WorkItem) -> dict[str, object]:
    creator = work_item.creator_user
    assignee = work_item.assignee_user
    timeline_start, timeline_end = _get_work_item_timeline_dates(work_item)
    duration_days = (timeline_end - timeline_start).days + 1
    
    contributors_dict = {}
    if hasattr(work_item, "activities"):
        for act in work_item.activities:
            if act.source_type == "SYSTEM_IMPORTED":
                continue
            actor = act.actor_user
            if actor and (not assignee or actor.id != assignee.id):
                contributors_dict[actor.id] = {
                    "id": actor.id,
                    "name": actor.name,
                    "profile_image_url": actor.profile_image_url
                }

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
        "parent_work_item_id": work_item.parent_work_item_id,
        "gantt_sort_order": work_item.gantt_sort_order,
        "creator": {
            "id": creator.id,
            "name": creator.name,
            "profile_image_url": creator.profile_image_url
        },
        "assignee": {
            "id": assignee.id,
            "name": assignee.name,
            "profile_image_url": assignee.profile_image_url
        }
        if assignee
        else None,
        "contributors": list(contributors_dict.values()),
    }


def _build_project_work_item_snapshot(
    session: Session,
    project_id: int,
) -> dict[str, object]:
    work_items = (
        session.query(models.WorkItem)
        .options(
            selectinload(models.WorkItem.activities).selectinload(models.Activity.actor_user)
        )
        .filter(models.WorkItem.project_id == project_id, models.WorkItem.deleted_at == None)
        .order_by(
            models.WorkItem.gantt_sort_order.asc(),
            models.WorkItem.created_at.asc(),
            models.WorkItem.id.asc(),
        )
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
        raise HTTPException(status_code=400, detail="종료일이 시작일보다 앞설 수 없습니다.")

    started_at = _combine_work_date(timeline_start_date)
    work_item.started_at = started_at

    work_item.due_date = timeline_end_date

    if status == "DONE":
        completed_at = _combine_work_date(timeline_end_date, end_of_day=True)
        if completed_at < started_at:
            completed_at = started_at
        work_item.completed_at = completed_at
    else:
        work_item.completed_at = None


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


def _ensure_work_item_parent(
    session: Session,
    project_id: int,
    work_item_id: int | None,
    parent_work_item_id: int | None,
) -> int | None:
    if parent_work_item_id is None:
        return None
    if work_item_id is not None and work_item_id == parent_work_item_id:
        raise HTTPException(status_code=400, detail="A work item cannot be its own parent.")

    parent = (
        session.query(models.WorkItem)
        .filter(
            models.WorkItem.project_id == project_id,
            models.WorkItem.id == parent_work_item_id,
            models.WorkItem.deleted_at == None,
        )
        .first()
    )
    if parent is None:
        raise HTTPException(status_code=400, detail="Parent work item must belong to this project.")
    return parent.id


def _ensure_parent_does_not_cycle(
    session: Session,
    project_id: int,
    work_item_id: int,
    parent_work_item_id: int | None,
) -> None:
    current_parent_id = parent_work_item_id
    seen: set[int] = set()
    while current_parent_id is not None:
        if current_parent_id == work_item_id:
            raise HTTPException(status_code=400, detail="Hierarchy cannot contain cycles.")
        if current_parent_id in seen:
            raise HTTPException(status_code=400, detail="Hierarchy cannot contain cycles.")
        seen.add(current_parent_id)
        current_parent_id = (
            session.query(models.WorkItem.parent_work_item_id)
            .filter(
                models.WorkItem.project_id == project_id,
                models.WorkItem.id == current_parent_id,
                models.WorkItem.deleted_at == None,
            )
            .scalar()
        )


def _validate_work_item_hierarchy(entries: list[WorkItemHierarchyEntryRequest]) -> None:
    entry_by_id = {entry.work_item_id: entry for entry in entries}
    if len(entry_by_id) != len(entries):
        raise HTTPException(status_code=400, detail="Hierarchy contains duplicate work items.")

    for entry in entries:
        if entry.gantt_sort_order < 0:
            raise HTTPException(status_code=400, detail="Hierarchy sort order cannot be negative.")
        if entry.parent_work_item_id is None:
            continue
        if entry.parent_work_item_id == entry.work_item_id:
            raise HTTPException(status_code=400, detail="A work item cannot be its own parent.")
        if entry.parent_work_item_id not in entry_by_id:
            raise HTTPException(status_code=400, detail="Parent work item must be included in hierarchy payload.")

    for entry in entries:
        seen: set[int] = set()
        current = entry
        while current.parent_work_item_id is not None:
            if current.work_item_id in seen:
                raise HTTPException(status_code=400, detail="Hierarchy cannot contain cycles.")
            seen.add(current.work_item_id)
            current = entry_by_id[current.parent_work_item_id]


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
            status=payload.status,
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
        parent_work_item_id = _ensure_work_item_parent(
            session,
            project_id,
            None,
            payload.parent_work_item_id,
        )
        gantt_sort_order = payload.gantt_sort_order
        if gantt_sort_order is None:
            max_sort_order = (
                session.query(func.max(models.WorkItem.gantt_sort_order))
                .filter(models.WorkItem.project_id == project_id, models.WorkItem.deleted_at == None)
                .scalar()
            )
            gantt_sort_order = int(max_sort_order or 0) + 1
        if gantt_sort_order < 0:
            raise HTTPException(status_code=400, detail="Hierarchy sort order cannot be negative.")
        now = datetime.now()

        work_item = models.WorkItem(
            project_id=project.id,
            creator_user_id=current_user.id,
            assignee_user_id=assignee_user_id,
            parent_work_item_id=parent_work_item_id,
            gantt_sort_order=gantt_sort_order,
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
        
        activity = models.Activity(
            project_id=project.id,
            work_items=[work_item],
            actor_user_id=current_user.id,
            activity_type="CONTENT_EDITING",
            contribution_phase="PREPARATION",
            title=f"'{work_item.title}' 추가됨",
            content="새 워크아이템이 생성되었습니다.",
            source_type="SYSTEM_IMPORTED",
            credibility_level="SYSTEM_IMPORTED",
            review_state="NORMAL",
            occurred_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(activity)
        
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

        if "parent_work_item_id" in changed_fields:
            parent_work_item_id = _ensure_work_item_parent(
                session,
                project_id,
                work_item.id,
                payload.parent_work_item_id,
            )
            _ensure_parent_does_not_cycle(session, project_id, work_item.id, parent_work_item_id)
            work_item.parent_work_item_id = parent_work_item_id

        if "gantt_sort_order" in changed_fields and payload.gantt_sort_order is not None:
            if payload.gantt_sort_order < 0:
                raise HTTPException(status_code=400, detail="Hierarchy sort order cannot be negative.")
            work_item.gantt_sort_order = payload.gantt_sort_order

        current_timeline_start, current_timeline_end = _get_work_item_timeline_dates(work_item)
        next_timeline_start = payload.timeline_start_date or current_timeline_start
        next_timeline_end = payload.timeline_end_date or current_timeline_end
        _apply_work_item_schedule(
            work_item,
            next_timeline_start,
            next_timeline_end,
            status=status_value,
        )
        now = datetime.now()
        work_item.updated_at = now

        activity = models.Activity(
            project_id=project_id,
            work_items=[work_item],
            actor_user_id=current_user.id,
            activity_type="CONTENT_EDITING",
            contribution_phase="REFINEMENT",
            title=f"'{work_item.title}' 업데이트됨",
            content="워크아이템의 정보가 변경되었습니다.",
            source_type="SYSTEM_IMPORTED",
            credibility_level="SYSTEM_IMPORTED",
            review_state="NORMAL",
            occurred_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(activity)

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
        
        now = datetime.now()
        activity = models.Activity(
            project_id=project_id,
            work_items=[],
            actor_user_id=current_user.id,
            activity_type="CONTENT_EDITING",
            contribution_phase="FINALIZATION",
            title=f"'{work_item.title}' 삭제됨",
            content="워크아이템이 프로젝트에서 삭제되었습니다.",
            source_type="SYSTEM_IMPORTED",
            credibility_level="SYSTEM_IMPORTED",
            review_state="NORMAL",
            occurred_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(activity)

        (
            session.query(models.WorkItem)
            .filter(
                models.WorkItem.project_id == project_id,
                models.WorkItem.parent_work_item_id == work_item.id,
                models.WorkItem.deleted_at == None,
            )
            .update(
                {
                    models.WorkItem.parent_work_item_id: None,
                    models.WorkItem.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        work_item.deleted_at = now
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


@router.put("/{project_id}/work-items/hierarchy", summary="Update project work item hierarchy")
def update_project_work_item_hierarchy(
    project_id: int,
    payload: UpdateWorkItemHierarchyRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, current_user.id)
        _validate_work_item_hierarchy(payload.items)

        work_items = (
            session.query(models.WorkItem)
            .filter(models.WorkItem.project_id == project_id, models.WorkItem.deleted_at == None)
            .all()
        )
        work_item_by_id = {work_item.id: work_item for work_item in work_items}
        payload_ids = {entry.work_item_id for entry in payload.items}
        active_ids = set(work_item_by_id)

        if payload_ids != active_ids:
            raise HTTPException(
                status_code=400,
                detail="Hierarchy payload must include every active project work item exactly once.",
            )

        now = datetime.now()
        for entry in payload.items:
            work_item = work_item_by_id[entry.work_item_id]
            work_item.parent_work_item_id = entry.parent_work_item_id
            work_item.gantt_sort_order = entry.gantt_sort_order
            work_item.updated_at = now

        session.commit()

        _broadcast_project_work_item_change(project_id, "hierarchy_updated")
        return {
            "message": "Work item hierarchy updated.",
            "project_id": project_id,
            "count": len(payload.items),
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
        session.close()

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
        try:
            session.close()
        except Exception:
            pass



@router.websocket("/{project_id}/presence/ws")
async def project_presence_events(
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
        
        user_info = {
            "id": current_user.id,
            "name": current_user.name,
            "profile_image_url": current_user.profile_image_url
        }
        session.close()

        await presence_manager.connect(project_id, user_info, websocket)

        while True:
            await websocket.receive_text()
    except HTTPException as exc:
        close_code = 4401 if exc.status_code == 401 else 4403
        await websocket.close(code=close_code)
    except WebSocketDisconnect:
        pass
    finally:
        await presence_manager.disconnect(project_id, websocket)
        try:
            session.close()
        except Exception:
            pass


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
            .filter(models.WorkItem.project_id == project_id, models.WorkItem.deleted_at == None)
            .order_by(models.WorkItem.created_at.asc())
            .all()
        )
        total_work_items = len(work_items)
        todo_count = sum(1 for work_item in work_items if work_item.status == "TODO")
        in_progress_count = sum(1 for work_item in work_items if work_item.status == "IN_PROGRESS")
        done_count = sum(1 for work_item in work_items if work_item.status == "DONE")
        completion_rate = int((done_count / total_work_items) * 100) if total_work_items else 0

        recent_activities = (
            session.query(models.Activity)
            .options(joinedload(models.Activity.work_items).joinedload(models.WorkItem.assignee_user))
            .options(joinedload(models.Activity.evidence_items))
            .options(joinedload(models.Activity.reactions))
            .options(joinedload(models.Activity.actor_user))
            .options(joinedload(models.Activity.target_user))
            .filter(
                models.Activity.project_id == project_id,
                models.Activity.source_type != "SYSTEM_IMPORTED"
            )
            .order_by(models.Activity.occurred_at.desc())
            .limit(20)
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
                    "recent_activities": [_serialize_activity(activity) for activity in recent_activities],
                },
            },
        }
    finally:
        session.close()


@router.patch("/{project_id}", summary="Update project")
def update_project(
    project_id: int, 
    payload: UpdateProjectRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        project, membership = _require_project_access(session, project_id, current_user.id)
        
        if membership.project_role != "LEADER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="팀장만 프로젝트 정보를 수정할 수 있습니다."
            )
            
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)
            
        session.commit()
        return {
            "status": "success",
            "project_id": project_id,
            "message": "Project updated successfully.",
        }
    finally:
        session.close()


@router.delete("/{project_id}", summary="Delete project")
def delete_project(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        project, membership = _require_project_access(session, project_id, current_user.id)
        
        if membership.project_role != "LEADER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="팀장만 프로젝트를 삭제할 수 있습니다."
            )
            
        session.delete(project)
        session.commit()
        return {
            "status": "success",
            "project_id": project_id,
            "message": "Project deleted successfully.",
        }
    finally:
        session.close()


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
def list_project_members(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, current_user.id)
        
        members = (
            session.query(models.ProjectMember, models.AppUser)
            .join(models.AppUser, models.ProjectMember.user_id == models.AppUser.id)
            .filter(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.left_at.is_(None)
            )
            .all()
        )
        
        items = []
        for mem, user in members:
            items.append({
                "project_member_id": mem.id,
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "profile_image_url": user.profile_image_url,
                "project_role": mem.project_role,
                "position_label": mem.position_label,
            })
            
        return {"items": items}
    finally:
        session.close()


@router.patch("/{project_id}/members/{member_id}", summary="Update project member")
def update_project_member(
    project_id: int,
    member_id: int,
    payload: UpdateProjectMemberRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, membership = _require_project_access(session, project_id, current_user.id)
        target_member = (
            session.query(models.ProjectMember)
            .filter(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.id == member_id,
                models.ProjectMember.left_at == None,
            )
            .first()
        )
        if target_member is None:
            raise HTTPException(status_code=404, detail="Project member not found.")

        is_self = target_member.user_id == current_user.id
        is_leader = membership.project_role == "LEADER"
        if not is_self and not is_leader:
            raise HTTPException(status_code=403, detail="Only leaders can update other members.")

        changed_fields = payload.model_fields_set
        if "position_label" in changed_fields and payload.position_label is not None:
            position_label = payload.position_label.strip()
            if not position_label:
                raise HTTPException(status_code=400, detail="Role is required.")
            if len(position_label) > 100:
                raise HTTPException(status_code=400, detail="Role must be 100 characters or fewer.")
            target_member.position_label = position_label

        if "memo" in changed_fields and is_leader:
            target_member.memo = payload.memo

        if "project_role" in changed_fields:
            if not is_leader:
                raise HTTPException(status_code=403, detail="Only leaders can update project permissions.")
            project_role = payload.project_role.upper() if payload.project_role else target_member.project_role
            if project_role not in ("LEADER", "MEMBER"):
                raise HTTPException(status_code=400, detail="Unsupported project role.")
            target_member.project_role = project_role

        session.commit()
        session.refresh(target_member)
        return {
            "status": "ok",
            "message": "Project member updated.",
            "member": _serialize_project_membership(target_member),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.delete("/{project_id}/members/{member_id}", summary="Leave or remove project member")
def remove_project_member(project_id: int, member_id: int) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "DELETE /api/projects/{project_id}/members/{member_id} will set left_at instead of hard delete.",
        "project_id": project_id,
        "member_id": member_id,
    }


@router.get("/{project_id}/join-requests", summary="List project join requests")
def list_project_join_requests(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, membership = _require_project_access(session, project_id, current_user.id)
        if membership.project_role != "LEADER":
            raise HTTPException(status_code=403, detail="Only LEADER can view join requests.")

        requests = (
            session.query(models.ProjectJoinRequest, models.AppUser)
            .join(models.AppUser, models.ProjectJoinRequest.requester_user_id == models.AppUser.id)
            .filter(
                models.ProjectJoinRequest.project_id == project_id,
                models.ProjectJoinRequest.request_status == 'PENDING',
            )
            .order_by(models.ProjectJoinRequest.created_at.desc())
            .all()
        )

        items = []
        for req, user in requests:
            items.append({
                "id": req.id,
                "project_id": req.project_id,
                "requester_user_id": req.requester_user_id,
                "requester_name": user.name,
                "requester_email": user.email,
                "request_message": req.request_message,
                "requested_position_label": req.requested_position_label,
                "request_status": req.request_status,
                "created_at": f"{req.created_at.isoformat()}Z" if req.created_at else None,
            })

        return {"items": items}
    finally:
        session.close()


@router.patch("/{project_id}/join-requests/{request_id}", summary="Review project join request")
def review_project_join_request(
    project_id: int,
    request_id: int,
    payload: ReviewProjectJoinRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, membership = _require_project_access(session, project_id, current_user.id)
        if membership.project_role != "LEADER":
            raise HTTPException(status_code=403, detail="Only LEADER can review join requests.")

        join_request = (
            session.query(models.ProjectJoinRequest)
            .filter(
                models.ProjectJoinRequest.id == request_id,
                models.ProjectJoinRequest.project_id == project_id,
                models.ProjectJoinRequest.request_status == 'PENDING',
            )
            .first()
        )
        if not join_request:
            raise HTTPException(status_code=404, detail="Join request not found or already reviewed.")

        now = func.now()
        status_value = payload.request_status.upper()
        if status_value not in ('APPROVED', 'REJECTED'):
            raise HTTPException(status_code=400, detail="Invalid request status. Must be APPROVED or REJECTED.")

        join_request.request_status = status_value
        join_request.reviewed_by_user_id = current_user.id
        join_request.reviewed_at = now
        join_request.review_note = payload.review_note

        if status_value == "APPROVED":
            project_role = payload.reviewed_project_role.upper() if payload.reviewed_project_role else "MEMBER"
            if project_role not in ("LEADER", "MEMBER"):
                project_role = "MEMBER"
            position_label = payload.reviewed_position_label.strip() if payload.reviewed_position_label else (join_request.requested_position_label or "팀원")

            join_request.reviewed_project_role = project_role
            join_request.reviewed_position_label = position_label

            # Check if user already member
            existing_member = session.query(models.ProjectMember).filter(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.user_id == join_request.requester_user_id,
                models.ProjectMember.left_at.is_(None)
            ).first()

            if not existing_member:
                new_member = models.ProjectMember(
                    project_id=project_id,
                    user_id=join_request.requester_user_id,
                    project_role=project_role,
                    position_label=position_label,
                    joined_at=now,
                )
                session.add(new_member)
            else:
                # If they somehow are already members and requested again, just resolve the request.
                pass
        
        session.commit()
        return {"status": "success", "message": f"Join request {status_value.lower()}."}
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@router.get("/{project_id}/activities", summary="List project activities")
def list_project_activities(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    author_scope: str = "ALL",
    category: str = "ALL",
    review_state: str = "ALL",
    contribution_phase: str = "ALL",
    credibility_level: str = "ALL",
    source_type: str = "MANUAL",
    work_item_id: int | None = None,
    work_item_ids: str | None = None,
    work_item_assignee_user_id: int | None = None,
    q: str | None = None,
    tag: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    has_evidence: bool | None = None,
    evidence_type: str = "ALL",
    has_reactions: bool | None = None,
    reaction_type: str = "ALL",
    reacted_by_me: bool | None = None,
    modified: bool | None = None,
    filter_operator: str = "AND",
    limit: int = 30,
    offset: int = 0,
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, current_user.id)

        query = (
            session.query(models.Activity)
            .options(joinedload(models.Activity.work_items).joinedload(models.WorkItem.assignee_user))
            .options(joinedload(models.Activity.evidence_items))
            .options(joinedload(models.Activity.reactions))
            .options(joinedload(models.Activity.actor_user))
            .options(joinedload(models.Activity.target_user))
            .filter(models.Activity.project_id == project_id)
        )

        if source_type != "ALL":
            query = query.filter(models.Activity.source_type == source_type.upper())
        conditions = []
        if author_scope.upper() == "ME":
            conditions.append(models.Activity.actor_user_id == current_user.id)
        elif actor_user_id is not None:
            conditions.append(models.Activity.actor_user_id == actor_user_id)
        if target_user_id is not None:
            conditions.append(models.Activity.target_user_id == target_user_id)
        if category != "ALL":
            conditions.append(models.Activity.activity_category == category.upper())
        if review_state != "ALL":
            conditions.append(models.Activity.review_state == review_state.upper())
        if contribution_phase != "ALL":
            conditions.append(models.Activity.contribution_phase == contribution_phase.upper())
        if credibility_level != "ALL":
            conditions.append(models.Activity.credibility_level == credibility_level.upper())

        parsed_work_item_ids = []
        if work_item_ids:
            for raw_id in work_item_ids.split(","):
                raw_id = raw_id.strip()
                if not raw_id:
                    continue
                try:
                    parsed_work_item_ids.append(int(raw_id))
                except ValueError:
                    continue
        if work_item_id is not None:
            conditions.append(models.Activity.work_items.any(models.WorkItem.id == work_item_id))
        elif parsed_work_item_ids:
            conditions.append(models.Activity.work_items.any(models.WorkItem.id.in_(parsed_work_item_ids)))
        if work_item_assignee_user_id is not None:
            conditions.append(
                models.Activity.work_items.any(
                    models.WorkItem.assignee_user_id == work_item_assignee_user_id
                )
            )

        keyword = q.strip() if q else ""
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(
                or_(
                    models.Activity.title.ilike(pattern),
                    models.Activity.content.ilike(pattern),
                    models.Activity.activity_type.ilike(pattern),
                )
            )

        tag_value = tag.strip() if tag else ""
        if tag_value:
            conditions.append(models.Activity.activity_type.ilike(f"%{tag_value}%"))

        date_conditions = []
        if date_from is not None:
            date_conditions.append(models.Activity.occurred_at >= datetime.combine(date_from, time.min))
        if date_to is not None:
            date_conditions.append(models.Activity.occurred_at <= datetime.combine(date_to, time.max))
        if date_conditions:
            conditions.append(and_(*date_conditions))

        if has_evidence is True:
            conditions.append(models.Activity.evidence_items.any())
        elif has_evidence is False:
            conditions.append(~models.Activity.evidence_items.any())
        if evidence_type != "ALL":
            conditions.append(
                models.Activity.evidence_items.any(
                    models.Evidence.evidence_type == evidence_type.upper()
                )
            )

        if has_reactions is True:
            conditions.append(models.Activity.reactions.any())
        elif has_reactions is False:
            conditions.append(~models.Activity.reactions.any())
        if reaction_type != "ALL":
            conditions.append(
                models.Activity.reactions.any(
                    models.ActivityReaction.reaction_type == reaction_type.upper()
                )
            )
        if reacted_by_me is True:
            conditions.append(
                models.Activity.reactions.any(
                    models.ActivityReaction.reactor_user_id == current_user.id
                )
            )
        elif reacted_by_me is False:
            conditions.append(
                ~models.Activity.reactions.any(
                    models.ActivityReaction.reactor_user_id == current_user.id
                )
            )

        if modified is True:
            conditions.append(models.Activity.updated_at > models.Activity.occurred_at)
        elif modified is False:
            conditions.append(models.Activity.updated_at <= models.Activity.occurred_at)

        if conditions:
            if filter_operator.upper() == "OR":
                query = query.filter(or_(*conditions))
            else:
                query = query.filter(*conditions)

        normalized_limit = min(max(limit, 1), 100)
        normalized_offset = max(offset, 0)
        total = query.count()
        activities = (
            query.order_by(models.Activity.occurred_at.desc(), models.Activity.id.desc())
            .offset(normalized_offset)
            .limit(normalized_limit)
            .all()
        )

        raw_activity_types = (
            session.query(models.Activity.activity_type)
            .filter(models.Activity.project_id == project_id, models.Activity.source_type != "SYSTEM_IMPORTED")
            .all()
        )
        tags = sorted(
            {
                tag_part.strip()
                for (activity_type,) in raw_activity_types
                for tag_part in (activity_type or "").split(",")
                if tag_part.strip()
            },
            key=lambda value: value.casefold(),
        )

        return {
            "project_id": project_id,
            "total": total,
            "count": len(activities),
            "limit": normalized_limit,
            "offset": normalized_offset,
            "has_more": normalized_offset + len(activities) < total,
            "items": [_serialize_activity(activity) for activity in activities],
            "available_tags": tags,
        }
    finally:
        session.close()


@router.post(
    "/{project_id}/activities",
    summary="Create an activity and optionally update task status",
    status_code=status.HTTP_201_CREATED
)
def create_activity(
    project_id: int,
    payload: ActivityCreateRequest,
    req: FastAPIRequest,
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict[str, object]:
    session = get_session()
    try:
        user = get_authenticated_user(request=req, session=session, authorization=authorization)
        user_id = user.id
        member = session.query(models.ProjectMember).filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.user_id == user_id
        ).first()
        if not member:
            return {"status": "error", "message": "Not a project member"}

        work_items = []
        if payload.work_item_ids:
            work_items = session.query(models.WorkItem).filter(
                models.WorkItem.project_id == project_id,
                models.WorkItem.id.in_(payload.work_item_ids)
            ).all()
            if len(work_items) != len(payload.work_item_ids):
                return {"status": "error", "message": "One or more WorkItems not found"}

        if payload.target_task_status == "DONE" and not payload.evidences:
             return {"status": "error", "message": "Evidence is required when completing a task."}

        now = datetime.now()
        is_reopening = False
        for work_item in work_items:
            if payload.target_task_status in ["TODO", "IN_PROGRESS"] and work_item.status == "DONE":
                is_reopening = True
                break

        new_activity = models.Activity(
            project_id=project_id,
            actor_user_id=user_id,
            target_user_id=payload.target_user_id,
            activity_category=payload.category,
            activity_type=payload.activity_type,
            contribution_phase=payload.contribution_phase,
            title=payload.title,
            content=payload.content,
            source_type="SYSTEM_IMPORTED" if is_reopening else "MANUAL",
            credibility_level="SYSTEM_IMPORTED" if is_reopening else "SELF_REPORTED",
            review_state="UNDER_REVIEW" if payload.category == "PEER_SUPPORT" else "NORMAL",
            occurred_at=now,
            created_at=now,
            updated_at=now
        )
        
        for w_item in work_items:
            new_activity.work_items.append(w_item)
            
        session.add(new_activity)
        session.flush()

        for ev_req in payload.evidences:
            if ev_req.evidence_type in ("LINK", "FILE") and (not ev_req.description or len(ev_req.description.strip()) < 10):
                 # enforcing logic but loosely for now
                 pass
            new_ev = models.Evidence(
                activity_id=new_activity.id,
                uploaded_by_user_id=user_id,
                evidence_type=ev_req.evidence_type,
                evidence_role=ev_req.evidence_role,
                description=ev_req.description,
                resource_url=ev_req.resource_url,
                file_name=ev_req.file_name,
                captured_at=now
            )
            session.add(new_ev)

        has_changed_status = False
        for w_item in work_items:
            if payload.target_task_status == "DONE":
                w_item.status = "DONE"
                has_changed_status = True
            elif payload.target_task_status == "IN_PROGRESS":
                w_item.status = "IN_PROGRESS"
                if not w_item.started_at:
                    w_item.started_at = now
                has_changed_status = True
            elif payload.target_task_status == "TODO":
                w_item.status = "TODO"
                has_changed_status = True

            if has_changed_status:
                session.add(w_item)
                
        session.commit()
        session.refresh(new_activity)

        if has_changed_status and len(work_items) > 0:
            try:
                # If we had a websocket connection loop we should notify here, but we will ignore it for now or do it later
                pass
            except Exception:
                pass

        return {
            "status": "created",
            "message": "Activity created successfully",
            "activity_id": new_activity.id,
            "work_item_status_changed": has_changed_status
        }
    except Exception as exc:
        session.rollback()
        return {"status": "error", "message": str(exc)}
    finally:
        session.close()


@router.put("/{project_id}/activities/{activity_id}")
def update_activity(
    project_id: int,
    activity_id: int,
    payload: dict,
    req: FastAPIRequest,
    authorization: str | None = Header(None, alias="Authorization"),
):
    session = get_session()
    try:
        user = get_authenticated_user(request=req, session=session, authorization=authorization)
        user_id = user.id
        activity = session.query(models.Activity).filter(
            models.Activity.project_id == project_id,
            models.Activity.id == activity_id
        ).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
        if activity.actor_user_id != user_id:
            raise HTTPException(status_code=403, detail="Only author can update")
        
        # Save revision history
        now = datetime.now()
        rev = models.ActivityRevisionHistory(
            activity_id=activity.id,
            edited_by_user_id=user_id,
            previous_title=activity.title,
            previous_content=activity.content,
            previous_contribution_phase=activity.contribution_phase,
            previous_credibility_level=activity.credibility_level,
            previous_review_state=activity.review_state,
            change_reason="User manually updated",
            edited_at=now
        )
        activity.updated_at = now
        session.add(rev)

        # Update fields
        if "content" in payload:
            activity.content = payload["content"]
        if "title" in payload:
            activity.title = payload["title"]
        if "activity_category" in payload:
            activity.activity_category = payload["activity_category"]
        if "activity_type" in payload:
            activity.activity_type = payload["activity_type"]
        if "work_item_ids" in payload:
            work_items = session.query(models.WorkItem).filter(
                models.WorkItem.project_id == project_id,
                models.WorkItem.id.in_(payload["work_item_ids"])
            ).all()
            activity.work_items = work_items
        if "target_user_id" in payload:
            activity.target_user_id = payload.get("target_user_id")
            
        if "evidences" in payload:
            session.query(models.Evidence).filter(models.Evidence.activity_id == activity.id).delete(synchronize_session=False)
            for ev_data in payload["evidences"]:
                session.add(models.Evidence(
                    activity_id=activity.id,
                    uploaded_by_user_id=user_id,
                    evidence_type=ev_data.get("evidence_type", "TEXT"),
                    description=ev_data.get("description"),
                    resource_url=ev_data.get("resource_url"),
                    evidence_role=ev_data.get("evidence_role", "SUPPORTING"),
                    verification_status="SELF_SUBMITTED",
                    captured_at=datetime.now()
                ))
        
        activity.last_edited_by_user_id = user_id
        activity.updated_at = datetime.now()
        
        session.commit()
        return {"status": "success"}
    except Exception as exc:
        session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        session.close()


@router.post("/{project_id}/activities/{activity_id}/approve")
def approve_peer_support_activity(
    project_id: int,
    activity_id: int,
    req: FastAPIRequest,
    authorization: str | None = Header(None, alias="Authorization"),
):
    session = get_session()
    try:
        user = get_authenticated_user(request=req, session=session, authorization=authorization)
        user_id = user.id
        
        activity = session.query(models.Activity).filter(
            models.Activity.project_id == project_id,
            models.Activity.id == activity_id
        ).first()
        
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
            
        if activity.target_user_id != user_id:
            raise HTTPException(status_code=403, detail="Only the target user can approve this peer support")
            
        if activity.review_state != "UNDER_REVIEW" or activity.activity_category != "PEER_SUPPORT":
            raise HTTPException(status_code=400, detail="Activity is not pending peer approval")
            
        activity.review_state = "RESOLVED"
        activity.credibility_level = "PEER_CONFIRMED"
        activity.updated_at = datetime.now()
        
        session.commit()
        return {"status": "success"}
    except Exception as exc:
        session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        session.close()


@router.delete("/{project_id}/activities/{activity_id}")
def delete_activity(
    project_id: int,
    activity_id: int,
    req: FastAPIRequest,
    authorization: str | None = Header(None, alias="Authorization"),
):
    session = get_session()
    try:
        user = get_authenticated_user(request=req, session=session, authorization=authorization)
        user_id = user.id
        activity = session.query(models.Activity).filter(
            models.Activity.project_id == project_id,
            models.Activity.id == activity_id
        ).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
        if activity.actor_user_id != user_id:
            # Check if leader
            member = session.query(models.ProjectMember).filter(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.user_id == user_id
            ).first()
            if not member or member.project_role != "LEADER":
                raise HTTPException(status_code=403, detail="Only author or LEADER can delete")
        
        session.delete(activity)
        session.commit()
        return {"status": "success"}
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        session.close()

class ActivityReactionRequest(BaseModel):
    reaction_type: str

@router.post("/{project_id}/activities/{activity_id}/reactions")
def toggle_activity_reaction(
    project_id: int,
    activity_id: int,
    payload: ActivityReactionRequest,
    req: FastAPIRequest,
    authorization: str | None = Header(None, alias="Authorization"),
):
    session = get_session()
    try:
        user = get_authenticated_user(request=req, session=session, authorization=authorization)
        
        valid_reactions = {"CONFIRMED", "HELPFUL", "AWESOME"}
        if payload.reaction_type not in valid_reactions:
            raise HTTPException(status_code=400, detail="Invalid reaction type")

        activity = session.query(models.Activity).filter(
            models.Activity.project_id == project_id,
            models.Activity.id == activity_id
        ).first()

        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found.")

        existing = session.query(models.ActivityReaction).filter(
            models.ActivityReaction.activity_id == activity_id,
            models.ActivityReaction.reactor_user_id == user.id,
            models.ActivityReaction.reaction_type == payload.reaction_type
        ).first()

        if existing:
            session.delete(existing)
        else:
            new_reaction = models.ActivityReaction(
                activity_id=activity_id,
                reactor_user_id=user.id,
                reaction_type=payload.reaction_type
            )
            session.add(new_reaction)

        session.commit()
        return {"status": "success"}
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        session.close()
