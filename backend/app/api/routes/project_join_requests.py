from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class CreateProjectJoinRequestRequest(BaseModel):
    join_code: str
    request_message: str | None = None
    requested_position_label: str | None = None


@router.post("", summary="Create project join request from join code")
def create_project_join_request(payload: CreateProjectJoinRequestRequest) -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "POST /api/project-join-requests will create a join request or auto-approve based on join policy.",
        "payload": payload.model_dump(exclude_none=True),
    }


@router.get("/me", summary="List current user's join requests")
def list_my_project_join_requests() -> dict[str, object]:
    return {
        "status": "not_implemented",
        "message": "GET /api/project-join-requests/me will list the current user's join requests.",
    }
