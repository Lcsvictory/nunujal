import asyncio
import json
from decimal import Decimal
from queue import Empty as QueueEmpty

from fastapi import APIRouter, Header, HTTPException, Request as FastAPIRequest, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

import app.models as models
from app.core.config import get_settings
from app.core.security import get_authenticated_user
from app.database import get_session
from app.services.contribution.evaluator import create_contribution_analysis_record
from app.services.contribution.queue import contribution_assessment_queue
from app.services.contribution.snapshot import build_stale_summary

router = APIRouter()


class ContributionObjectionRequest(BaseModel):
    content: str


def _decimal_to_float(value: Decimal | None) -> float:
    return float(value or 0)


def _get_active_membership(
    session: Session,
    project_id: int,
    user_id: int,
) -> models.ProjectMember | None:
    return (
        session.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.user_id == user_id,
            models.ProjectMember.left_at == None,
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
    membership = _get_active_membership(session, project_id, user_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Only active project members can access this project.")
    return project, membership


def _can_view_feedback_review(
    review: models.FeedbackReview,
    membership: models.ProjectMember,
    user_id: int,
) -> bool:
    if membership.project_role == "LEADER":
        return True
    if review.author_user_id == user_id:
        return True
    if review.target_user_id == user_id:
        return True
    if review.target_user_id is None and review.contribution_result and review.contribution_result.target_user_id == user_id:
        return True
    return False


def _serialize_feedback_review(
    review: models.FeedbackReview,
) -> dict[str, object]:
    return {
        "id": review.id,
        "request_type": review.request_type,
        "request_status": review.request_status,
        "ai_impact_mode": review.ai_impact_mode,
        "content": review.content,
        "resolution_note": review.resolution_note,
        "created_at": review.created_at.isoformat(),
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "author": {
            "id": review.author_user.id,
            "name": review.author_user.name,
            "profile_image_url": review.author_user.profile_image_url,
        }
        if review.author_user
        else None,
        "target_user": {
            "id": review.target_user.id,
            "name": review.target_user.name,
            "profile_image_url": review.target_user.profile_image_url,
        }
        if review.target_user
        else None,
        "contribution_result_id": review.contribution_result_id,
    }


def _serialize_contribution_result(
    result: models.ContributionResult,
    membership: models.ProjectMember | None = None,
    user_id: int | None = None,
) -> dict[str, object]:
    visible_feedback_reviews = result.feedback_reviews
    if membership is not None and user_id is not None:
        visible_feedback_reviews = [
            review
            for review in result.feedback_reviews
            if _can_view_feedback_review(review, membership, user_id)
        ]
    return {
        "id": result.id,
        "target_user": {
            "id": result.target_user.id,
            "name": result.target_user.name,
            "profile_image_url": result.target_user.profile_image_url,
        }
        if result.target_user
        else None,
        "reference_score": _decimal_to_float(result.reference_score),
        "confidence_score": _decimal_to_float(result.confidence_score),
        "result_status": result.result_status,
        "execution_score": _decimal_to_float(result.execution_score),
        "collaboration_score": _decimal_to_float(result.collaboration_score),
        "documentation_score": _decimal_to_float(result.documentation_score),
        "problem_solving_score": _decimal_to_float(result.problem_solving_score),
        "disputed_activity_count": result.disputed_activity_count,
        "down_weighted_activity_count": result.down_weighted_activity_count,
        "summary": result.summary,
        "rationale": result.rationale,
        "public_explanation": result.public_explanation,
        "uncertainty_note": result.uncertainty_note,
        "warning_note": result.warning_note,
        "created_at": result.created_at.isoformat(),
        "feedback_reviews": [
            _serialize_feedback_review(review)
            for review in sorted(visible_feedback_reviews, key=lambda item: item.created_at, reverse=True)
        ],
    }


def _serialize_analysis(
    analysis: models.AiAnalysis | None,
    membership: models.ProjectMember | None = None,
    user_id: int | None = None,
) -> dict[str, object] | None:
    if analysis is None:
        return None
    results = sorted(
        analysis.contribution_results,
        key=lambda result: result.reference_score,
        reverse=True,
    )
    return {
        "id": analysis.id,
        "project_id": analysis.project_id,
        "requested_by_user_id": analysis.requested_by_user_id,
        "analysis_start_date": analysis.analysis_start_date.isoformat(),
        "analysis_end_date": analysis.analysis_end_date.isoformat(),
        "model_name": analysis.model_name,
        "prompt_version": analysis.prompt_version,
        "policy_version": analysis.policy_version,
        "analysis_mode": analysis.analysis_mode,
        "snapshot_at": analysis.snapshot_at.isoformat(),
        "status": analysis.status,
        "input_summary": analysis.input_summary,
        "disclaimer": analysis.disclaimer,
        "created_at": analysis.created_at.isoformat(),
        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "results": [
            _serialize_contribution_result(result, membership, user_id)
            for result in results
        ],
    }


def _analysis_query(session: Session, project_id: int):
    return (
        session.query(models.AiAnalysis)
        .options(
            joinedload(models.AiAnalysis.contribution_results)
            .joinedload(models.ContributionResult.target_user)
        )
        .options(
            joinedload(models.AiAnalysis.contribution_results)
            .joinedload(models.ContributionResult.feedback_reviews)
            .joinedload(models.FeedbackReview.author_user)
        )
        .options(
            joinedload(models.AiAnalysis.contribution_results)
            .joinedload(models.ContributionResult.feedback_reviews)
            .joinedload(models.FeedbackReview.target_user)
        )
        .filter(models.AiAnalysis.project_id == project_id)
        .order_by(models.AiAnalysis.id.desc())
    )


def _latest_completed_analysis(session: Session, project_id: int) -> models.AiAnalysis | None:
    return (
        _analysis_query(session, project_id)
        .filter(models.AiAnalysis.status == "COMPLETED")
        .first()
    )


def _latest_active_analysis(session: Session, project_id: int) -> models.AiAnalysis | None:
    base_query = _analysis_query(session, project_id).order_by(None)
    processing = (
        base_query
        .filter(models.AiAnalysis.status == "PROCESSING")
        .order_by(models.AiAnalysis.created_at.asc(), models.AiAnalysis.id.asc())
        .first()
    )
    if processing is not None:
        return processing
    return (
        base_query
        .filter(models.AiAnalysis.status == "REQUESTED")
        .order_by(models.AiAnalysis.created_at.asc(), models.AiAnalysis.id.asc())
        .first()
    )


def _latest_pending_analysis_for_user(
    session: Session,
    project_id: int,
    user_id: int,
) -> models.AiAnalysis | None:
    return (
        _analysis_query(session, project_id)
        .filter(
            models.AiAnalysis.requested_by_user_id == user_id,
            models.AiAnalysis.status.in_(["REQUESTED", "PROCESSING"]),
        )
        .first()
    )


def _build_latest_contribution_payload(
    session: Session,
    project_id: int,
    membership: models.ProjectMember,
    user_id: int,
) -> dict[str, object]:
    latest = _latest_completed_analysis(session, project_id)
    active_analysis = _latest_active_analysis(session, project_id)
    my_pending_analysis = _latest_pending_analysis_for_user(session, project_id, user_id)
    dispute_review_query = (
        session.query(models.FeedbackReview)
        .options(joinedload(models.FeedbackReview.author_user))
        .options(joinedload(models.FeedbackReview.target_user))
        .filter(
            models.FeedbackReview.project_id == project_id,
            models.FeedbackReview.request_type == "RESULT_DISPUTE",
        )
    )
    visible_dispute_reviews = [
        review
        for review in dispute_review_query.all()
        if _can_view_feedback_review(review, membership, user_id)
    ]
    open_reviews = (
        sorted(
            [
                review
                for review in visible_dispute_reviews
                if review.request_status in ("OPEN", "UNDER_REVIEW")
            ],
            key=lambda review: (review.created_at, review.id),
            reverse=True,
        )
    )
    recent_reviews = (
        sorted(
            [
                review
                for review in visible_dispute_reviews
                if review.request_status in ("OPEN", "UNDER_REVIEW", "REFLECTED")
            ],
            key=lambda review: (review.created_at, review.id),
            reverse=True,
        )[:10]
    )
    return {
        "analysis": _serialize_analysis(latest, membership, user_id),
        "active_analysis": _serialize_analysis(active_analysis, membership, user_id),
        "can_assess": membership.project_role == "LEADER",
        "is_leader": membership.project_role == "LEADER",
        "has_my_pending_assessment": my_pending_analysis is not None,
        "my_user_id": user_id,
        "stale": build_stale_summary(session, project_id),
        "open_feedback_reviews": [_serialize_feedback_review(review) for review in open_reviews],
        "recent_feedback_reviews": [_serialize_feedback_review(review) for review in recent_reviews],
    }


def _load_latest_contribution_payload_for_user(project_id: int, user_id: int) -> dict[str, object]:
    session = get_session()
    try:
        _project, membership = _require_project_access(session, project_id, user_id)
        return _build_latest_contribution_payload(session, project_id, membership, user_id)
    finally:
        session.close()


def _format_sse(event_name: str, payload: dict[str, object]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _contribution_payload_signature(payload: dict[str, object]) -> str:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else None
    active_analysis = payload.get("active_analysis") if isinstance(payload.get("active_analysis"), dict) else None
    open_reviews = payload.get("open_feedback_reviews") if isinstance(payload.get("open_feedback_reviews"), list) else []
    recent_reviews = payload.get("recent_feedback_reviews") if isinstance(payload.get("recent_feedback_reviews"), list) else []

    def analysis_signature(value: dict[str, object] | None) -> dict[str, object] | None:
        if value is None:
            return None
        return {
            "id": value.get("id"),
            "status": value.get("status"),
            "completed_at": value.get("completed_at"),
        }

    def review_signature(value: object) -> dict[str, object] | None:
        if not isinstance(value, dict):
            return None
        return {
            "id": value.get("id"),
            "request_status": value.get("request_status"),
            "reviewed_at": value.get("reviewed_at"),
            "resolution_note": value.get("resolution_note"),
        }

    return json.dumps(
        {
            "analysis": analysis_signature(analysis),
            "active_analysis": analysis_signature(active_analysis),
            "open_reviews": [review_signature(review) for review in open_reviews],
            "recent_reviews": [review_signature(review) for review in recent_reviews],
            "has_my_pending_assessment": payload.get("has_my_pending_assessment"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


@router.get("/{project_id}/contribution/latest", summary="Get latest contribution assessment")
def get_latest_contribution(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        user = get_authenticated_user(session, request, authorization)
        _project, membership = _require_project_access(session, project_id, user.id)
        return _build_latest_contribution_payload(session, project_id, membership, user.id)
    finally:
        session.close()



def _ensure_contribution_stream_session_is_active(
    project_id: int,
    expected_user_id: int,
    request: FastAPIRequest,
    authorization: str | None,
) -> None:
    session = get_session()
    try:
        user = get_authenticated_user(session, request, authorization)
        if user.id != expected_user_id:
            raise HTTPException(status_code=401, detail="Session user changed.")
        _require_project_access(session, project_id, user.id)
    finally:
        session.close()

@router.get("/{project_id}/contribution/events", summary="Subscribe contribution assessment events")
async def stream_contribution_events(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    session = get_session()
    try:
        user = get_authenticated_user(session, request, authorization)
        _project, _membership = _require_project_access(session, project_id, user.id)
        user_id = user.id
    finally:
        session.close()

    subscriber = contribution_assessment_queue.subscribe(project_id)

    async def event_generator():
        try:
            initial_payload = _load_latest_contribution_payload_for_user(project_id, user_id)
            last_payload_signature = _contribution_payload_signature(initial_payload)
            yield _format_sse(
                "contribution",
                {"type": "snapshot", "event": None, "payload": initial_payload},
            )

            while True:
                if await request.is_disconnected():
                    break

                try:
                    _ensure_contribution_stream_session_is_active(
                        project_id,
                        user_id,
                        request,
                        authorization,
                    )
                except HTTPException as exc:
                    yield _format_sse("contribution_error", {"detail": exc.detail})
                    break

                try:
                    queue_event = await asyncio.to_thread(subscriber.get, True, 5)
                except QueueEmpty:
                    try:
                        payload = _load_latest_contribution_payload_for_user(project_id, user_id)
                    except HTTPException as exc:
                        yield _format_sse("contribution_error", {"detail": exc.detail})
                        break

                    next_payload_signature = _contribution_payload_signature(payload)
                    if next_payload_signature != last_payload_signature:
                        last_payload_signature = next_payload_signature
                        yield _format_sse(
                            "contribution",
                            {
                                "type": "snapshot",
                                "event": {
                                    "type": "snapshot",
                                    "project_id": project_id,
                                    "analysis_id": None,
                                    "status": None,
                                },
                                "payload": payload,
                            },
                        )
                        continue
                    yield ": heartbeat\n\n"
                    continue

                try:
                    payload = _load_latest_contribution_payload_for_user(project_id, user_id)
                except HTTPException as exc:
                    yield _format_sse("contribution_error", {"detail": exc.detail})
                    break

                yield _format_sse(
                    "contribution",
                    {
                        "type": queue_event["type"],
                        "event": queue_event,
                        "payload": payload,
                    },
                )
                last_payload_signature = _contribution_payload_signature(payload)
        finally:
            contribution_assessment_queue.unsubscribe(project_id, subscriber)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{project_id}/contribution/analyses", summary="List contribution assessment history")
def list_contribution_analyses(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    try:
        user = get_authenticated_user(session, request, authorization)
        _project, membership = _require_project_access(session, project_id, user.id)
        analyses = _analysis_query(session, project_id).limit(20).all()
        return {
            "items": [
                _serialize_analysis(analysis, membership, user.id)
                for analysis in analyses
            ]
        }
    finally:
        session.close()


@router.post("/{project_id}/contribution/assess", summary="Run contribution assessment")
def run_assessment(
    project_id: int,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    session = get_session()
    settings = get_settings()
    try:
        user = get_authenticated_user(session, request, authorization)
        project, membership = _require_project_access(session, project_id, user.id)
        if membership.project_role != "LEADER":
            raise HTTPException(status_code=403, detail="Only project leaders can request contribution assessment.")
        existing_analysis = _latest_pending_analysis_for_user(session, project_id, user.id)
        if existing_analysis is not None:
            return {
                "analysis": _serialize_analysis(existing_analysis, membership, user.id),
                "queued": True,
                "already_queued": True,
            }

        analysis = create_contribution_analysis_record(
            session,
            project,
            user,
            mode="REGULAR",
            settings=settings,
        )
        session.commit()
        contribution_assessment_queue.enqueue(analysis.id)
        contribution_assessment_queue.publish(
            project_id,
            "queued",
            analysis_id=analysis.id,
            status=analysis.status,
        )
        session.refresh(analysis)
        analysis = _analysis_query(session, project_id).filter(models.AiAnalysis.id == analysis.id).first()
        return {"analysis": _serialize_analysis(analysis, membership, user.id), "queued": True}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post(
    "/{project_id}/contribution/results/{result_id}/objections",
    summary="Create a contribution objection and re-assess immediately",
    status_code=status.HTTP_201_CREATED,
)
def create_contribution_objection(
    project_id: int,
    result_id: int,
    payload: ContributionObjectionRequest,
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Objection content is required.")

    session = get_session()
    settings = get_settings()
    try:
        user = get_authenticated_user(session, request, authorization)
        project, membership = _require_project_access(session, project_id, user.id)
        result = (
            session.query(models.ContributionResult)
            .options(joinedload(models.ContributionResult.target_user))
            .join(models.AiAnalysis, models.AiAnalysis.id == models.ContributionResult.analysis_id)
            .filter(
                models.AiAnalysis.project_id == project_id,
                models.ContributionResult.id == result_id,
            )
            .first()
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Contribution result not found.")

        review = models.FeedbackReview(
            project_id=project_id,
            author_user_id=user.id,
            target_user_id=result.target_user_id,
            contribution_result_id=result.id,
            request_type="RESULT_DISPUTE",
            visibility="LEADER_ONLY",
            requester_hidden_from_target=False,
            content=content,
            request_status="OPEN",
            ai_impact_mode="REQUIRE_REANALYSIS",
        )
        session.add(review)
        session.commit()

        analysis = create_contribution_analysis_record(
            session,
            project,
            user,
            mode="DISPUTE_AWARE",
            settings=settings,
        )
        session.commit()
        contribution_assessment_queue.enqueue(analysis.id)
        contribution_assessment_queue.publish(
            project_id,
            "queued",
            analysis_id=analysis.id,
            status=analysis.status,
        )

        session.refresh(analysis)
        analysis = _analysis_query(session, project_id).filter(models.AiAnalysis.id == analysis.id).first()
        return {
            "feedback_review": _serialize_feedback_review(review),
            "analysis": _serialize_analysis(analysis, membership, user.id),
            "queued": True,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
