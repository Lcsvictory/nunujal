from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

import app.models as models


def _decimal_to_float(value: Decimal | None) -> float:
    return float(value or 0)


def get_latest_completed_analysis(
    session: Session,
    project_id: int,
) -> models.AiAnalysis | None:
    return (
        session.query(models.AiAnalysis)
        .options(joinedload(models.AiAnalysis.contribution_results).joinedload(models.ContributionResult.target_user))
        .filter(
            models.AiAnalysis.project_id == project_id,
            models.AiAnalysis.status == "COMPLETED",
        )
        .order_by(models.AiAnalysis.completed_at.desc().nullslast(), models.AiAnalysis.created_at.desc(), models.AiAnalysis.id.desc())
        .first()
    )


def _review_target_user_id(review: models.FeedbackReview) -> int | None:
    if review.target_user_id is not None:
        return review.target_user_id
    if review.contribution_result is not None:
        return review.contribution_result.target_user_id
    return None


def _build_dispute_scope(open_feedback_reviews: list[models.FeedbackReview]) -> tuple[set[int], list[dict[str, Any]]]:
    relevant_user_ids: set[int] = set()
    scope_reviews: list[dict[str, Any]] = []
    for review in open_feedback_reviews:
        target_user_id = _review_target_user_id(review)
        review_user_ids = {review.author_user_id}
        if target_user_id is not None:
            review_user_ids.add(target_user_id)
        relevant_user_ids.update(review_user_ids)
        scope_reviews.append(
            {
                "review_id": review.id,
                "author_user_id": review.author_user_id,
                "author_name": review.author_user.name if review.author_user else "",
                "target_user_id": target_user_id,
                "target_name": review.target_user.name if review.target_user else (
                    review.contribution_result.target_user.name
                    if review.contribution_result and review.contribution_result.target_user
                    else None
                ),
                "is_self_objection": target_user_id == review.author_user_id,
                "included_user_ids": sorted(review_user_ids),
            }
        )
    return relevant_user_ids, scope_reviews


def _serialize_related_work_item(work_item: models.WorkItem, relevant_user_ids: set[int]) -> dict[str, Any]:
    contributors: dict[int, dict[str, Any]] = {}
    for activity in work_item.activities:
        if activity.source_type == "SYSTEM_IMPORTED" or activity.actor_user_id not in relevant_user_ids:
            continue
        if activity.actor_user is None:
            continue
        contributors[activity.actor_user_id] = {
            "user_id": activity.actor_user_id,
            "name": activity.actor_user.name,
        }

    return {
        "id": work_item.id,
        "title": work_item.title,
        "description": work_item.description,
        "status": work_item.status,
        "priority": work_item.priority,
        "creator_user_id": work_item.creator_user_id,
        "creator_name": work_item.creator_user.name if work_item.creator_user else "",
        "assignee_user_id": work_item.assignee_user_id,
        "assignee_name": work_item.assignee_user.name if work_item.assignee_user else None,
        "started_at": work_item.started_at.isoformat() if work_item.started_at else None,
        "completed_at": work_item.completed_at.isoformat() if work_item.completed_at else None,
        "updated_at": work_item.updated_at.isoformat(),
        "related_activity_count": sum(
            1
            for activity in work_item.activities
            if activity.source_type != "SYSTEM_IMPORTED" and activity.actor_user_id in relevant_user_ids
        ),
        "related_contributors": list(contributors.values()),
    }


def build_contribution_snapshot(
    session: Session,
    project: models.Project,
    *,
    mode: str,
    requested_by_user_id: int,
) -> dict[str, Any]:
    latest_analysis = get_latest_completed_analysis(session, project.id)
    members = (
        session.query(models.ProjectMember)
        .options(joinedload(models.ProjectMember.user))
        .filter(models.ProjectMember.project_id == project.id, models.ProjectMember.left_at == None)
        .order_by(models.ProjectMember.project_role.desc(), models.ProjectMember.id.asc())
        .all()
    )
    member_ids = [member.user_id for member in members]

    open_feedback_reviews = (
        session.query(models.FeedbackReview)
        .options(joinedload(models.FeedbackReview.author_user))
        .options(joinedload(models.FeedbackReview.target_user))
        .options(joinedload(models.FeedbackReview.contribution_result).joinedload(models.ContributionResult.target_user))
        .filter(
            models.FeedbackReview.project_id == project.id,
            models.FeedbackReview.request_type == "RESULT_DISPUTE",
            models.FeedbackReview.request_status.in_(["OPEN", "UNDER_REVIEW"]),
        )
        .order_by(models.FeedbackReview.created_at.asc(), models.FeedbackReview.id.asc())
        .all()
    )
    relevant_user_ids, dispute_scope_reviews = _build_dispute_scope(open_feedback_reviews)
    is_dispute_scoped = mode == "DISPUTE_AWARE" and bool(relevant_user_ids)

    activities_query = (
        session.query(models.Activity)
        .options(joinedload(models.Activity.actor_user))
        .options(joinedload(models.Activity.target_user))
        .options(selectinload(models.Activity.work_items).joinedload(models.WorkItem.assignee_user))
        .filter(
            models.Activity.project_id == project.id,
            models.Activity.source_type != "SYSTEM_IMPORTED",
        )
    )
    if is_dispute_scoped:
        activities_query = activities_query.filter(
            or_(
                models.Activity.actor_user_id.in_(relevant_user_ids),
                models.Activity.target_user_id.in_(relevant_user_ids),
            )
        )
    elif latest_analysis is not None:
        activities_query = activities_query.filter(models.Activity.updated_at > latest_analysis.snapshot_at)

    changed_activities = (
        activities_query.order_by(models.Activity.occurred_at.asc(), models.Activity.id.asc())
        .limit(120)
        .all()
    )

    all_activity_counts = dict(
        session.query(models.Activity.actor_user_id, func.count(models.Activity.id))
        .filter(
            models.Activity.project_id == project.id,
            models.Activity.source_type != "SYSTEM_IMPORTED",
        )
        .group_by(models.Activity.actor_user_id)
        .all()
    )
    changed_activity_count = activities_query.count()

    member_activity_summary: dict[int, dict[str, Any]] = {
        member.user_id: {
            "activity_count_total": int(all_activity_counts.get(member.user_id, 0)),
            "changed_activity_count": 0,
            "changed_activity_titles": [],
        }
        for member in members
    }
    for activity in changed_activities:
        summary = member_activity_summary.get(activity.actor_user_id)
        if summary is None:
            continue
        summary["changed_activity_count"] += 1
        summary["changed_activity_titles"].append(activity.title)

    related_work_items = []
    if is_dispute_scoped:
        related_work_items = (
            session.query(models.WorkItem)
            .options(joinedload(models.WorkItem.creator_user))
            .options(joinedload(models.WorkItem.assignee_user))
            .options(selectinload(models.WorkItem.activities).joinedload(models.Activity.actor_user))
            .filter(
                models.WorkItem.project_id == project.id,
                models.WorkItem.deleted_at == None,
                or_(
                    models.WorkItem.creator_user_id.in_(relevant_user_ids),
                    models.WorkItem.assignee_user_id.in_(relevant_user_ids),
                    models.WorkItem.activities.any(
                        or_(
                            models.Activity.actor_user_id.in_(relevant_user_ids),
                            models.Activity.target_user_id.in_(relevant_user_ids),
                        )
                    ),
                ),
            )
            .order_by(models.WorkItem.updated_at.desc(), models.WorkItem.id.desc())
            .limit(80)
            .all()
        )

    all_open_dispute_count = (
        session.query(models.FeedbackReview)
        .filter(
            models.FeedbackReview.project_id == project.id,
            models.FeedbackReview.request_type == "RESULT_DISPUTE",
            models.FeedbackReview.request_status.in_(["OPEN", "UNDER_REVIEW"]),
        )
        .count()
    )

    previous_results = []
    if latest_analysis is not None:
        for result in latest_analysis.contribution_results:
            previous_result = {
                "user_id": result.target_user_id,
                "name": result.target_user.name if result.target_user else "",
                "contribution_percent": _decimal_to_float(result.reference_score),
                "summary": result.summary,
                "result_status": result.result_status,
            }
            if not is_dispute_scoped:
                previous_result.update(
                    {
                        "confidence_score": _decimal_to_float(result.confidence_score),
                        "rationale": result.rationale,
                        "public_explanation": result.public_explanation,
                        "uncertainty_note": result.uncertainty_note,
                        "warning_note": result.warning_note,
                    }
                )
            previous_results.append(previous_result)

    return {
        "analysis_mode": mode,
        "requested_by_user_id": requested_by_user_id,
        "dispute_scope": {
            "enabled": is_dispute_scoped,
            "rule": (
                "OPEN/UNDER_REVIEW 상태의 RESULT_DISPUTE만 재산정 근거로 사용한다. "
                "본인 기여도 이의제기는 해당 사용자 활동/할일만 포함하고, "
                "타인 기여도 이의제기는 이의제기 작성자와 대상자의 활동/할일만 포함한다. "
                "REFLECTED/REJECTED/PARTIALLY_REFLECTED 등 이미 처리된 이의제기는 입력에서 제외한다."
            ),
            "relevant_user_ids": sorted(relevant_user_ids),
            "reviews": dispute_scope_reviews,
        },
        "project": {
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "status": project.status,
            "start_date": project.start_date.isoformat(),
            "end_date": project.end_date.isoformat(),
        },
        "members": [
            {
                "user_id": member.user_id,
                "name": member.user.name,
                "project_role": member.project_role,
                "position_label": member.position_label,
                "activity_summary": member_activity_summary.get(member.user_id, {}),
            }
            for member in members
        ],
        "latest_analysis": {
            "id": latest_analysis.id,
            "snapshot_at": latest_analysis.snapshot_at.isoformat(),
            "analysis_mode": latest_analysis.analysis_mode,
            "completed_at": latest_analysis.completed_at.isoformat() if latest_analysis.completed_at else None,
            **({} if is_dispute_scoped else {"input_summary": latest_analysis.input_summary}),
        }
        if latest_analysis
        else None,
        "previous_contribution_results": previous_results,
        "changed_activity_count_since_latest_analysis": changed_activity_count if latest_analysis else len(changed_activities),
        "activity_scope": "open_result_dispute_related_users" if is_dispute_scoped else "changed_since_latest_analysis",
        "related_work_items": [
            _serialize_related_work_item(work_item, relevant_user_ids)
            for work_item in related_work_items
        ],
        "changed_activities": [
            {
                "id": activity.id,
                "actor_user_id": activity.actor_user_id,
                "actor_name": activity.actor_user.name if activity.actor_user else "",
                "target_user_id": activity.target_user_id,
                "target_name": activity.target_user.name if activity.target_user else None,
                "activity_category": activity.activity_category,
                "activity_type": activity.activity_type,
                "contribution_phase": activity.contribution_phase,
                "review_state": activity.review_state,
                "title": activity.title,
                "content": activity.content,
                "occurred_at": activity.occurred_at.isoformat(),
                "updated_at": activity.updated_at.isoformat(),
                "work_items": [
                    {
                        "id": work_item.id,
                        "title": work_item.title,
                        "status": work_item.status,
                        "priority": work_item.priority,
                        "assignee_user_id": work_item.assignee_user_id,
                        "assignee_name": work_item.assignee_user.name if work_item.assignee_user else None,
                    }
                    for work_item in activity.work_items
                ],
            }
            for activity in changed_activities
        ],
        "open_feedback_reviews": [
            {
                "id": review.id,
                "request_type": review.request_type,
                "author_user_id": review.author_user_id,
                "author_name": review.author_user.name if review.author_user else "",
                "target_user_id": review.target_user_id,
                "target_name": review.target_user.name if review.target_user else None,
                "contribution_result_target_user_id": review.contribution_result.target_user_id if review.contribution_result else None,
                "content": review.content,
                "created_at": review.created_at.isoformat(),
            }
            for review in open_feedback_reviews
        ],
        "rules": {
            "definition": "프로젝트 목표 달성에 실제로 기여한 활동을 역할, 난이도, 품질, 협업까지 고려해 평가한 상대적 지분이다.",
            "ignore_evidence": True,
            "total_percent": 100,
            "must_include_user_ids": member_ids,
            "open_result_dispute_count": all_open_dispute_count,
        },
    }


def build_stale_summary(
    session: Session,
    project_id: int,
) -> dict[str, Any]:
    latest_analysis = get_latest_completed_analysis(session, project_id)
    if latest_analysis is None:
        return {
            "needs_reassessment": True,
            "reason": "아직 기여도 평가가 없습니다.",
            "changed_activity_count": 0,
            "days_since_latest_analysis": None,
            "open_dispute_count": 0,
        }

    changed_activity_count = (
        session.query(models.Activity)
        .filter(
            models.Activity.project_id == project_id,
            models.Activity.source_type != "SYSTEM_IMPORTED",
            models.Activity.updated_at > latest_analysis.snapshot_at,
        )
        .count()
    )
    open_dispute_count = (
        session.query(models.FeedbackReview)
        .filter(
            models.FeedbackReview.project_id == project_id,
            models.FeedbackReview.request_type == "RESULT_DISPUTE",
            models.FeedbackReview.request_status.in_(["OPEN", "UNDER_REVIEW"]),
        )
        .count()
    )
    days_since = (datetime.now() - latest_analysis.snapshot_at).days
    needs = (
        changed_activity_count >= 50
        or (changed_activity_count > 0 and days_since >= 7)
        or (open_dispute_count > 0 and changed_activity_count >= 10)
    )
    reason = ""
    if changed_activity_count >= 50:
        reason = "마지막 평가 이후 활동이 50개 이상 추가/수정되었습니다."
    elif changed_activity_count > 0 and days_since >= 7:
        reason = "마지막 평가 이후 7일 이상 지났고 새 활동이 있습니다."
    elif open_dispute_count > 0 and changed_activity_count >= 10:
        reason = "열린 이의제기가 있고 새 활동이 10개 이상 있습니다."

    return {
        "needs_reassessment": needs,
        "reason": reason,
        "changed_activity_count": changed_activity_count,
        "days_since_latest_analysis": days_since,
        "open_dispute_count": open_dispute_count,
    }
