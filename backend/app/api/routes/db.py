from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

import app.models as models
from app.database import get_engine, get_session

router = APIRouter()


class CreateUserRequest(BaseModel):
    provider: str
    provider_user_id: str
    email: str
    name: str
    student_id: str | None = None
    department: str | None = None
    profile_image_url: str | None = None
    status: str = "ACTIVE"
def create_tables() -> None:
    engine = get_engine()
    models.Base.metadata.create_all(bind=engine)


def insert_dummy_data(session: Session) -> dict[str, int | str]:
    existing_seed_user = (
        session.query(models.AppUser)
        .filter(models.AppUser.provider_user_id == "dummy_google_leader_001")
        .first()
    )
    if existing_seed_user:
        return {"status": "skipped", "message": "Dummy data already exists."}

    now = datetime.now()

    leader = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_leader_001",
        email="leader@nunujal.com",
        name="Kim Nunu",
        student_id="20260001",
        department="Computer Science",
        profile_image_url="https://example.com/profiles/leader.png",
        status="ACTIVE",
        last_login_at=now,
    )
    member = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_member_001",
        email="member@nunujal.com",
        name="Park Jaljal",
        student_id="20260002",
        department="AI Engineering",
        profile_image_url="https://example.com/profiles/member.png",
        status="ACTIVE",
        last_login_at=now - timedelta(hours=2),
    )
    reviewer = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_reviewer_001",
        email="reviewer@nunujal.com",
        name="Lee Review",
        student_id="20260003",
        department="Software Engineering",
        profile_image_url="https://example.com/profiles/reviewer.png",
        status="ACTIVE",
        last_login_at=now - timedelta(days=1),
    )
    candidate = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_candidate_001",
        email="candidate@nunujal.com",
        name="Choi Candidate",
        student_id="20260004",
        department="Product Design",
        profile_image_url="https://example.com/profiles/candidate.png",
        status="ACTIVE",
        last_login_at=now - timedelta(hours=6),
    )
    session.add_all([leader, member, reviewer, candidate])
    session.flush()

    project = models.Project(
        title="NunuJal Dummy Project",
        description="Project for ORM and dummy data validation.",
        created_by_user_id=leader.id,
        join_code="TEAM42",
        join_code_active=True,
        join_policy="LEADER_APPROVE",
        join_code_created_at=now,
        join_code_expires_at=now + timedelta(days=30),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status="IN_PROGRESS",
    )
    session.add(project)
    session.flush()

    project_members = [
        models.ProjectMember(
            project_id=project.id,
            user_id=leader.id,
            project_role="LEADER",
            position_label="Team Lead",
            memo="Overall project owner",
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=member.id,
            project_role="MEMBER",
            position_label="Frontend Developer",
            memo="UI implementation owner",
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=reviewer.id,
            project_role="MEMBER",
            position_label="Reviewer",
            memo="Validation and review owner",
        ),
    ]
    session.add_all(project_members)
    session.flush()

    join_request = models.ProjectJoinRequest(
        project_id=project.id,
        requester_user_id=candidate.id,
        request_message="프론트엔드와 발표 자료 정리를 맡고 싶습니다.",
        requested_position_label="디자인 및 발표",
        request_status="PENDING",
    )
    session.add(join_request)
    session.flush()

    work_item_1 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=member.id,
        title="Implement login screen",
        description="Build frontend login page and connect Google OAuth entry button.",
        status="IN_PROGRESS",
        priority="HIGH",
        due_date=date(2026, 4, 10),
        started_at=now - timedelta(days=2),
        created_at=now - timedelta(days=3),
    )
    work_item_2 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=reviewer.id,
        title="Review ORM models",
        description="Validate model structure and constraints.",
        status="TODO",
        priority="MEDIUM",
        due_date=date(2026, 4, 15),
        started_at=now - timedelta(days=1),
        created_at=now - timedelta(days=2),
    )
    session.add_all([work_item_1, work_item_2])
    session.flush()

    work_item_dependency = models.WorkItemDependency(
        project_id=project.id,
        predecessor_work_item_id=work_item_1.id,
        successor_work_item_id=work_item_2.id,
    )
    session.add(work_item_dependency)
    session.flush()

    activity_1 = models.Activity(
        project_id=project.id,
        work_item_id=work_item_1.id,
        actor_user_id=member.id,
        activity_type="CONTENT_EDITING",
        contribution_phase="DRAFTING",
        title="Drafted login UI",
        content="Structured login card layout and button hierarchy.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=1, hours=3),
        last_edited_by_user_id=member.id,
        correction_reason="Updated copy and spacing.",
    )
    activity_2 = models.Activity(
        project_id=project.id,
        work_item_id=work_item_2.id,
        actor_user_id=reviewer.id,
        activity_type="MEETING_RECORD",
        contribution_phase="REFINEMENT",
        title="ORM review meeting",
        content="Reviewed model relationships and dummy data strategy.",
        source_type="MANUAL",
        credibility_level="PEER_CONFIRMED",
        review_state="UNDER_REVIEW",
        occurred_at=now - timedelta(hours=10),
        last_edited_by_user_id=reviewer.id,
        correction_reason="Refined summary after review.",
    )
    session.add_all([activity_1, activity_2])
    session.flush()

    revision = models.ActivityRevisionHistory(
        activity_id=activity_2.id,
        edited_by_user_id=reviewer.id,
        previous_title="ORM review",
        previous_content="Initial model review completed.",
        previous_contribution_phase="REFINEMENT",
        previous_credibility_level="SELF_REPORTED",
        previous_review_state="NORMAL",
        change_reason="Expanded meeting details.",
    )
    session.add(revision)
    session.flush()

    analysis = models.AiAnalysis(
        project_id=project.id,
        requested_by_user_id=leader.id,
        analysis_start_date=date(2026, 3, 1),
        analysis_end_date=date(2026, 4, 3),
        model_name="gpt-5.4",
        prompt_version="v1",
        policy_version="v1",
        analysis_mode="DISPUTE_AWARE",
        snapshot_at=now,
        disputed_activity_count=1,
        low_credibility_activity_count=0,
        excluded_activity_count=0,
        status="COMPLETED",
        input_summary="Includes activity logs and feedback review context.",
        disclaimer="Generated from dummy data only.",
        created_at=now,
        completed_at=now,
    )
    session.add(analysis)
    session.flush()

    contribution_result_1 = models.ContributionResult(
        analysis_id=analysis.id,
        target_user_id=member.id,
        reference_score=Decimal("82.50"),
        confidence_score=Decimal("74.00"),
        result_status="NORMAL",
        execution_score=Decimal("85.00"),
        collaboration_score=Decimal("78.00"),
        documentation_score=Decimal("80.00"),
        problem_solving_score=Decimal("87.00"),
        disputed_activity_count=0,
        down_weighted_activity_count=0,
        summary="High implementation contribution.",
        rationale="Most of the login and OAuth entry work was handled by this user.",
        public_explanation="Implementation contribution was confirmed.",
        uncertainty_note="Some items may still require review.",
        warning_note="Dummy data generated result.",
    )
    contribution_result_2 = models.ContributionResult(
        analysis_id=analysis.id,
        target_user_id=reviewer.id,
        reference_score=Decimal("70.00"),
        confidence_score=Decimal("66.50"),
        result_status="UNDER_REVIEW",
        execution_score=Decimal("68.00"),
        collaboration_score=Decimal("72.00"),
        documentation_score=Decimal("74.00"),
        problem_solving_score=Decimal("69.00"),
        disputed_activity_count=1,
        down_weighted_activity_count=1,
        summary="Review and validation contribution.",
        rationale="Review contribution exists, but one activity is still under review.",
        public_explanation="Review-stage contribution was partially reflected.",
        uncertainty_note="Review-state activity lowers confidence.",
        warning_note="Needs additional verification.",
    )
    session.add_all([contribution_result_1, contribution_result_2])
    session.flush()

    feedback_review_1 = models.FeedbackReview(
        project_id=project.id,
        author_user_id=leader.id,
        target_user_id=member.id,
        activity_id=activity_1.id,
        request_type="SUPPLEMENT",
        visibility="LEADER_ONLY",
        requester_hidden_from_target=True,
        content="Please add more detail to the login UI change log.",
        request_status="OPEN",
        ai_impact_mode="LOWER_CONFIDENCE_ONLY",
    )
    feedback_review_2 = models.FeedbackReview(
        project_id=project.id,
        author_user_id=member.id,
        target_user_id=reviewer.id,
        contribution_result_id=contribution_result_2.id,
        request_type="RESULT_DISPUTE",
        visibility="LEADER_ONLY",
        requester_hidden_from_target=False,
        content="The review contribution seems undervalued. Please re-check the result.",
        request_status="UNDER_REVIEW",
        ai_impact_mode="REQUIRE_REANALYSIS",
        reviewed_by_user_id=leader.id,
        created_at=now,
        reviewed_at=now,
        resolution_note="Reanalysis pending.",
    )
    session.add_all([feedback_review_1, feedback_review_2])
    session.flush()

    evidence_items = [
        models.Evidence(
            activity_id=activity_1.id,
            uploaded_by_user_id=member.id,
            evidence_type="IMAGE",
            evidence_role="SUPPORTING",
            file_name="login-ui.png",
            resource_url="https://example.com/evidence/login-ui.png",
            description="Screenshot of the login UI draft.",
            integrity_hash="sha256-login-ui",
            verification_status="SELF_SUBMITTED",
            captured_at=now - timedelta(days=1),
        ),
        models.Evidence(
            feedback_review_id=feedback_review_2.id,
            uploaded_by_user_id=reviewer.id,
            evidence_type="LINK",
            evidence_role="SUPPORTING",
            resource_url="https://example.com/evidence/review-note",
            description="Review note document link.",
            verification_status="VERIFIED",
            captured_at=now - timedelta(hours=8),
        ),
    ]
    session.add_all(evidence_items)
    session.commit()

    return {
        "status": "created",
        "users": 4,
        "projects": 1,
        "project_join_requests": 1,
        "project_members": 3,
        "work_items": 2,
        "work_item_dependencies": 1,
        "activities": 2,
        "activity_revisions": 1,
        "ai_analyses": 1,
        "contribution_results": 2,
        "feedback_reviews": 2,
        "evidence_items": 2,
    }


def create_tables_and_seed_dummy_data() -> dict[str, int | str]:
    create_tables()
    session = get_session()
    try:
        return insert_dummy_data(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.get("/drop-and-create", summary="Databases reset (drop and create tables)")
def databases() -> dict[str, str]:
    models.Base.metadata.drop_all(bind=get_engine())
    create_tables()
    return {"tables": "dropped and created."}


@router.post("/users", summary="Create app user manually")
def create_user(payload: CreateUserRequest) -> dict[str, str | int]:
    session = get_session()
    try:
        existing_user = (
            session.query(models.AppUser)
            .filter(
                (models.AppUser.provider == payload.provider)
                & (models.AppUser.provider_user_id == payload.provider_user_id)
            )
            .first()
        )
        if existing_user:
            return {"status": "skipped", "message": "User already exists.", "user_id": existing_user.id}

        user = models.AppUser(
            provider=payload.provider,
            provider_user_id=payload.provider_user_id,
            email=payload.email,
            name=payload.name,
            student_id=payload.student_id,
            department=payload.department,
            profile_image_url=payload.profile_image_url,
            status=payload.status,
            last_login_at=datetime.now(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"status": "created", "message": "User saved.", "user_id": user.id}
    except Exception as exc:
        session.rollback()
        return {"status": "error", "message": str(exc)}
    finally:
        session.close()


@router.get("/users", summary="List app users")
def list_users() -> dict[str, list[dict[str, str | int | None]]]:
    session = get_session()
    try:
        users = session.query(models.AppUser).all()
        return {
            "users": [
                {
                    "id": user.id,
                    "provider": user.provider,
                    "provider_user_id": user.provider_user_id,
                    "email": user.email,
                    "name": user.name,
                    "student_id": user.student_id,
                    "department": user.department,
                    "status": user.status,
                }
                for user in users
            ]
        }
    finally:
        session.close()


@router.get("/seed", summary="Create tables and insert dummy data")
def seed_dummy_data() -> dict[str, int | str]:
    try:
        return create_tables_and_seed_dummy_data()
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/test", summary="Database Connection Test")
def db_test() -> dict[str, str]:
    session = get_session()
    try:
        user = session.query(models.AppUser).first()
        if not user:
            return {"status": "ok", "message": "Database connection successful, but no users found."}
        return {"status": "ok", "message": f"Database connection successful. First user: {user.email}"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    finally:
        session.close()
