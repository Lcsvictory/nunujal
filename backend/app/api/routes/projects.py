from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


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


@router.get("", summary="List projects for current user")
def list_projects() -> dict[str, object]:
    return {"status": "not_implemented", "message": "GET /api/projects will list the current user's projects."}


@router.post("", summary="Create project")
def create_project(payload: CreateProjectRequest) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "POST /api/projects will create a project and issue a join code.",
        "payload": payload.model_dump(),
    }


@router.get("/{project_id}", summary="Get project detail")
def get_project(project_id: int) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "GET /api/projects/{project_id} will return project detail.",
        "project_id": project_id,
    }


@router.patch("/{project_id}", summary="Update project")
def update_project(project_id: int, payload: UpdateProjectRequest) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "PATCH /api/projects/{project_id} will update project metadata.",
        "project_id": project_id,
        "payload": payload.model_dump(exclude_none=True),
    }


@router.get("/join-preview/{join_code}", summary="Preview project by join code")
def preview_project_by_join_code(join_code: str) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "GET /api/projects/join-preview/{join_code} will preview a project before join request.",
        "join_code": join_code,
    }


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
