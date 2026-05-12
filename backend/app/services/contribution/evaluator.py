from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import app.models as models
from app.core.config import Settings
from app.services.contribution.prompts import (
    CONTRIBUTION_RESPONSE_SCHEMA,
    build_system_prompt,
    build_user_prompt,
)
from app.services.contribution.providers.base import ContributionAiProvider
from app.services.contribution.snapshot import build_contribution_snapshot


logger = logging.getLogger("uvicorn.error")

ALLOWED_RESULT_STATUSES = {"NORMAL", "LOW_CONFIDENCE", "UNDER_REVIEW", "DISPUTED"}


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid numeric score from AI: {value}") from exc


def _clamp_score(value: Any) -> Decimal:
    score = _to_decimal(value)
    if score < 0:
        return Decimal("0.00")
    if score > 100:
        return Decimal("100.00")
    return score


def _normalize_contribution_scores(members: list[dict[str, Any]]) -> None:
    raw_scores = [_clamp_score(member.get("contribution_percent")) for member in members]
    total = sum(raw_scores, Decimal("0.00"))
    if total <= 0:
        equal = (Decimal("100.00") / Decimal(len(members))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        normalized = [equal for _ in members]
    else:
        normalized = [
            (score * Decimal("100.00") / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for score in raw_scores
        ]

    diff = Decimal("100.00") - sum(normalized, Decimal("0.00"))
    normalized[-1] = (normalized[-1] + diff).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    for member, score in zip(members, normalized):
        member["contribution_percent"] = score


def _validate_ai_result(
    result: dict[str, Any],
    *,
    active_user_ids: set[int],
) -> list[dict[str, Any]]:
    members = result.get("members")
    if not isinstance(members, list) or not members:
        raise HTTPException(status_code=502, detail="AI result does not contain member scores.")

    by_user_id: dict[int, dict[str, Any]] = {}
    for member in members:
        if not isinstance(member, dict):
            raise HTTPException(status_code=502, detail="AI member result must be an object.")
        try:
            user_id = int(member.get("user_id"))
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI member result contains an invalid user_id.") from exc
        if user_id not in active_user_ids:
            continue
        by_user_id[user_id] = member

    missing = active_user_ids - set(by_user_id)
    if missing:
        raise HTTPException(status_code=502, detail=f"AI result is missing active members: {sorted(missing)}")

    normalized_members = [by_user_id[user_id] for user_id in sorted(active_user_ids)]
    _normalize_contribution_scores(normalized_members)
    return normalized_members


def _string_value(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _format_score(value: Decimal | None) -> str:
    return f"{_clamp_score(value or 0):.2f}".rstrip("0").rstrip(".")


def _build_dispute_resolution_note(
    *,
    base_summary: str,
    open_reviews: list[models.FeedbackReview],
    previous_scores: dict[int, Decimal],
    new_scores: dict[int, Decimal],
) -> str:
    lines = [base_summary]
    for review in open_reviews:
        target_user_id = review.target_user_id
        if target_user_id is None and review.contribution_result is not None:
            target_user_id = review.contribution_result.target_user_id
        if target_user_id is None:
            continue

        before_score = previous_scores.get(target_user_id)
        after_score = new_scores.get(target_user_id)
        target_name = (
            review.target_user.name
            if review.target_user
            else review.contribution_result.target_user.name
            if review.contribution_result and review.contribution_result.target_user
            else f"사용자 {target_user_id}"
        )
        if before_score is not None and after_score is not None:
            diff = after_score - before_score
            direction = "변동 없음"
            if diff > 0:
                direction = f"+{_format_score(diff)}%p"
            elif diff < 0:
                direction = f"{_format_score(diff)}%p"
            lines.append(
                f"{target_name}: 기존 {_format_score(before_score)}% -> 재산정 {_format_score(after_score)}% ({direction})"
            )
        elif after_score is not None:
            lines.append(f"{target_name}: 재산정 {_format_score(after_score)}%")

    return "\n".join(lines)


def _latest_completed_result_text_by_user(
    session: Session,
    project_id: int,
) -> dict[int, dict[str, str | None]]:
    latest_analysis = (
        session.query(models.AiAnalysis)
        .options(joinedload(models.AiAnalysis.contribution_results))
        .filter(
            models.AiAnalysis.project_id == project_id,
            models.AiAnalysis.status == "COMPLETED",
        )
        .order_by(models.AiAnalysis.completed_at.desc(), models.AiAnalysis.id.desc())
        .first()
    )
    if latest_analysis is None:
        return {}

    return {
        result.target_user_id: {
            "summary": result.summary,
            "rationale": result.rationale,
            "public_explanation": result.public_explanation,
            "uncertainty_note": result.uncertainty_note,
            "warning_note": result.warning_note,
        }
        for result in latest_analysis.contribution_results
    }


def run_contribution_assessment(
    session: Session,
    project: models.Project,
    requested_by_user: models.AppUser,
    *,
    mode: str,
    provider: ContributionAiProvider,
    settings: Settings,
) -> models.AiAnalysis:
    analysis = create_contribution_analysis_record(
        session,
        project,
        requested_by_user,
        mode=mode,
        settings=settings,
    )
    return process_contribution_analysis(
        session,
        analysis,
        provider=provider,
        settings=settings,
    )


def create_contribution_analysis_record(
    session: Session,
    project: models.Project,
    requested_by_user: models.AppUser,
    *,
    mode: str,
    settings: Settings,
) -> models.AiAnalysis:
    open_feedback_count = (
        session.query(models.FeedbackReview)
        .filter(
            models.FeedbackReview.project_id == project.id,
            models.FeedbackReview.request_type == "RESULT_DISPUTE",
            models.FeedbackReview.request_status.in_(["OPEN", "UNDER_REVIEW"]),
        )
        .count()
    )
    now = datetime.now()
    analysis = models.AiAnalysis(
        project_id=project.id,
        requested_by_user_id=requested_by_user.id,
        analysis_start_date=project.start_date,
        analysis_end_date=min(project.end_date, date.today()),
        model_name=settings.contribution_model_name,
        prompt_version=settings.contribution_prompt_version,
        policy_version=settings.contribution_policy_version,
        analysis_mode=mode,
        snapshot_at=now,
        disputed_activity_count=open_feedback_count,
        low_credibility_activity_count=0,
        excluded_activity_count=0,
        status="REQUESTED",
        input_summary="AI 기여도 평가가 큐에 등록되었습니다.",
        disclaimer="AI가 활동 기록을 기반으로 산정한 참고용 결과입니다. 증거 자료는 평가에 사용하지 않습니다.",
        created_at=now,
    )
    session.add(analysis)
    session.flush()
    return analysis


def process_contribution_analysis(
    session: Session,
    analysis: models.AiAnalysis,
    *,
    provider: ContributionAiProvider,
    settings: Settings,
) -> models.AiAnalysis:
    project = session.query(models.Project).filter(models.Project.id == analysis.project_id).first()
    requested_by_user = session.query(models.AppUser).filter(models.AppUser.id == analysis.requested_by_user_id).first()
    if project is None or requested_by_user is None:
        analysis.status = "FAILED"
        analysis.input_summary = "프로젝트 또는 요청자를 찾을 수 없어 평가를 실행하지 못했습니다."
        analysis.completed_at = datetime.now()
        session.flush()
        return analysis

    active_members = (
        session.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == analysis.project_id, models.ProjectMember.left_at == None)
        .all()
    )
    active_user_ids = {member.user_id for member in active_members}
    if not active_user_ids:
        raise HTTPException(status_code=400, detail="Project has no active members.")

    snapshot = build_contribution_snapshot(
        session,
        project,
        mode=analysis.analysis_mode,
        requested_by_user_id=analysis.requested_by_user_id,
    )
    preserved_result_text_by_user = (
        _latest_completed_result_text_by_user(session, project.id)
        if analysis.analysis_mode == "DISPUTE_AWARE"
        else {}
    )
    analysis.status = "PROCESSING"
    analysis.input_summary = "AI 기여도 평가 결과를 생성 중입니다."
    analysis.snapshot_at = datetime.now()
    analysis.disputed_activity_count = len(snapshot.get("open_feedback_reviews", []))
    session.flush()

    try:
        ai_result = provider.evaluate(
            model=settings.contribution_model_name,
            system_prompt=build_system_prompt(),
            user_prompt=build_user_prompt(snapshot),
            response_schema=CONTRIBUTION_RESPONSE_SCHEMA,
        )
        member_results = _validate_ai_result(ai_result, active_user_ids=active_user_ids)
        previous_scores = {
            int(result.get("user_id")): _clamp_score(result.get("contribution_percent"))
            for result in snapshot.get("previous_contribution_results", [])
            if isinstance(result, dict) and result.get("user_id") is not None
        }

        analysis.input_summary = _string_value(ai_result.get("input_summary"), "활동 요약을 기반으로 평가했습니다.")
        analysis.disclaimer = _string_value(
            ai_result.get("summary"),
            "AI가 활동 기록을 기반으로 산정한 참고용 결과입니다.",
        )
        analysis.status = "COMPLETED"
        analysis.completed_at = datetime.now()
        new_scores: dict[int, Decimal] = {}

        for member_result in member_results:
            target_user_id = int(member_result["user_id"])
            contribution_percent = member_result["contribution_percent"]
            new_scores[target_user_id] = _clamp_score(contribution_percent)
            preserved_text = preserved_result_text_by_user.get(target_user_id, {})
            result_status = _string_value(member_result.get("result_status"), "NORMAL").upper()
            if result_status not in ALLOWED_RESULT_STATUSES:
                result_status = "NORMAL"
            contribution_result = models.ContributionResult(
                analysis_id=analysis.id,
                target_user_id=target_user_id,
                reference_score=contribution_percent,
                confidence_score=_clamp_score(member_result.get("confidence_score", 70)),
                result_status=result_status,
                execution_score=_clamp_score(member_result.get("execution_score", 0)),
                collaboration_score=_clamp_score(member_result.get("collaboration_score", 0)),
                documentation_score=_clamp_score(member_result.get("documentation_score", 0)),
                problem_solving_score=_clamp_score(member_result.get("problem_solving_score", 0)),
                disputed_activity_count=1 if result_status == "DISPUTED" else 0,
                down_weighted_activity_count=0,
                summary=_string_value(preserved_text.get("summary") or member_result.get("summary"), "요약 없음"),
                rationale=_string_value(preserved_text.get("rationale") or member_result.get("rationale"), "근거 없음"),
                public_explanation=_string_value(
                    preserved_text.get("public_explanation") or member_result.get("public_explanation"),
                    "설명 없음",
                ),
                uncertainty_note=_string_value(
                    preserved_text.get("uncertainty_note")
                    if preserved_text.get("uncertainty_note") is not None
                    else member_result.get("uncertainty_note")
                ),
                warning_note=_string_value(
                    preserved_text.get("warning_note")
                    if preserved_text.get("warning_note") is not None
                    else member_result.get("warning_note")
                ),
            )
            session.add(contribution_result)

        if analysis.analysis_mode == "DISPUTE_AWARE":
            open_reviews = (
                session.query(models.FeedbackReview)
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
            resolution_note = _build_dispute_resolution_note(
                base_summary=_string_value(
                ai_result.get("dispute_resolution_summary"),
                "이의제기를 포함해 재평가했습니다.",
                ),
                open_reviews=open_reviews,
                previous_scores=previous_scores,
                new_scores=new_scores,
            )
            now = datetime.now()
            for review in open_reviews:
                review.request_status = "REFLECTED"
                review.reviewed_by_user_id = requested_by_user.id
                review.reviewed_at = now
                review.resolution_note = resolution_note
                review.updated_at = now
        session.flush()
        return analysis
    except Exception as exc:
        analysis.status = "FAILED"
        analysis.completed_at = datetime.now()
        analysis.input_summary = f"AI 기여도 평가 실패: {exc}"
        logger.exception(
            "AI 기여도 평가 처리 중 실패했습니다. project_id=%s analysis_id=%s",
            analysis.project_id,
            analysis.id,
        )
        session.flush()
        return analysis
