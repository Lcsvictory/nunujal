from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import app.models as models
from app.core.security import get_authenticated_user
from app.database import get_session

router = APIRouter()


class CreateProjectJoinRequestRequest(BaseModel):
    join_code: str
    request_message: str | None = None
    requested_position_label: str | None = None


@router.post("", summary="Create project join request from join code", status_code=status.HTTP_201_CREATED)
def create_project_join_request(
    payload: CreateProjectJoinRequestRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        normalized_join_code = payload.join_code.strip().upper()
        if not normalized_join_code:
            raise HTTPException(status_code=400, detail="Join code is required.")

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

        existing_membership = (
            session.query(models.ProjectMember)
            .filter(
                models.ProjectMember.project_id == project.id,
                models.ProjectMember.user_id == current_user.id,
            )
            .first()
        )
        if existing_membership and existing_membership.left_at is None:
            raise HTTPException(status_code=409, detail="You are already an active member of this project.")

        requested_position_label = (payload.requested_position_label or "").strip() or "Team Member"
        request_message = (payload.request_message or "").strip() or None
        now = datetime.now()

        join_request = (
            session.query(models.ProjectJoinRequest)
            .filter(
                models.ProjectJoinRequest.project_id == project.id,
                models.ProjectJoinRequest.requester_user_id == current_user.id,
            )
            .first()
        )

        if project.join_policy == "AUTO_APPROVE":
            if existing_membership is None:
                existing_membership = models.ProjectMember(
                    project_id=project.id,
                    user_id=current_user.id,
                    project_role="MEMBER",
                    position_label=requested_position_label,
                    joined_at=now,
                    memo=request_message,
                )
                session.add(existing_membership)
            else:
                existing_membership.project_role = "MEMBER"
                existing_membership.position_label = requested_position_label
                existing_membership.joined_at = now
                existing_membership.left_at = None
                existing_membership.memo = request_message

            if join_request is None:
                join_request = models.ProjectJoinRequest(
                    project_id=project.id,
                    requester_user_id=current_user.id,
                    request_message=request_message,
                    requested_position_label=requested_position_label,
                    request_status="APPROVED",
                    reviewed_project_role="MEMBER",
                    reviewed_position_label=requested_position_label,
                    review_note="Automatically approved by project join policy.",
                    reviewed_at=now,
                )
                session.add(join_request)
            else:
                join_request.request_message = request_message
                join_request.requested_position_label = requested_position_label
                join_request.request_status = "APPROVED"
                join_request.reviewed_by_user_id = None
                join_request.reviewed_project_role = "MEMBER"
                join_request.reviewed_position_label = requested_position_label
                join_request.review_note = "Automatically approved by project join policy."
                join_request.reviewed_at = now
                join_request.updated_at = now

            response_message = "Join request was auto-approved and you were added to the project."
            membership_created = True
        else:
            if join_request and join_request.request_status == "PENDING":
                raise HTTPException(status_code=409, detail="A pending join request already exists for this project.")

            if join_request is None:
                join_request = models.ProjectJoinRequest(
                    project_id=project.id,
                    requester_user_id=current_user.id,
                    request_message=request_message,
                    requested_position_label=requested_position_label,
                    request_status="PENDING",
                )
                session.add(join_request)
            else:
                join_request.request_message = request_message
                join_request.requested_position_label = requested_position_label
                join_request.request_status = "PENDING"
                join_request.reviewed_by_user_id = None
                join_request.reviewed_project_role = None
                join_request.reviewed_position_label = None
                join_request.review_note = None
                join_request.reviewed_at = None
                join_request.updated_at = now

            response_message = "Join request submitted."
            membership_created = False

        session.commit()
        session.refresh(join_request)

        return {
            "message": response_message,
            "membership_created": membership_created,
            "project": {
                "id": project.id,
                "title": project.title,
                "status": project.status,
                "join_policy": project.join_policy,
            },
            "join_request": {
                "id": join_request.id,
                "project_id": join_request.project_id,
                "request_status": join_request.request_status,
                "requested_position_label": join_request.requested_position_label,
                "reviewed_project_role": join_request.reviewed_project_role,
                "reviewed_position_label": join_request.reviewed_position_label,
            },
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.get("/me", summary="List current user's join requests")
def list_my_project_join_requests(
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        current_user = get_authenticated_user(session, request, authorization)
        join_requests = (
            session.query(models.ProjectJoinRequest, models.Project)
            .join(models.Project, models.Project.id == models.ProjectJoinRequest.project_id)
            .filter(models.ProjectJoinRequest.requester_user_id == current_user.id)
            .order_by(models.ProjectJoinRequest.created_at.desc())
            .all()
        )

        return {
            "join_requests": [
                {
                    "id": join_request.id,
                    "request_status": join_request.request_status,
                    "requested_position_label": join_request.requested_position_label,
                    "created_at": join_request.created_at.isoformat(),
                    "project": {
                        "id": project.id,
                        "title": project.title,
                        "status": project.status,
                    },
                }
                for join_request, project in join_requests
            ]
        }
    finally:
        session.close()
