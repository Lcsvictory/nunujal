from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import inspect, text
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
    ensure_work_item_hierarchy_columns()


def ensure_work_item_hierarchy_columns() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    if not inspector.has_table("work_item"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("work_item")}
    dialect_name = engine.dialect.name

    with engine.begin() as connection:
        if "parent_work_item_id" not in existing_columns:
            if dialect_name == "sqlite":
                connection.execute(
                    text("ALTER TABLE work_item ADD COLUMN parent_work_item_id BIGINT REFERENCES work_item(id) ON DELETE SET NULL")
                )
            else:
                connection.execute(text("ALTER TABLE work_item ADD COLUMN parent_work_item_id BIGINT NULL"))
                connection.execute(
                    text(
                        "ALTER TABLE work_item "
                        "ADD CONSTRAINT fk_work_item_parent "
                        "FOREIGN KEY (parent_work_item_id) REFERENCES work_item(id) ON DELETE SET NULL"
                    )
                )

        if "gantt_sort_order" not in existing_columns:
            connection.execute(
                text("ALTER TABLE work_item ADD COLUMN gantt_sort_order INTEGER NOT NULL DEFAULT 0")
            )


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
        email="nunu@nunujal.com",
        name="김누누",
        student_id="20260001",
        department="컴퓨터공학과",
        profile_image_url="https://picsum.photos/seed/1232/200",
        status="ACTIVE",
        last_login_at=now,
    )
    member = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_member_001",
        email="jaljal@nunujal.com",
        name="박잘잘",
        student_id="20260002",
        department="인공지능학과",
        profile_image_url="https://picsum.photos/seed/76653/200",
        status="ACTIVE",
        last_login_at=now - timedelta(hours=2),
    )
    reviewer = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_reviewer_001",
        email="review@nunujal.com",
        name="이리뷰",
        student_id="20260003",
        department="소프트웨어학과",
        profile_image_url="https://picsum.photos/seed/45334/200",
        status="ACTIVE",
        last_login_at=now - timedelta(days=1),
    )
    candidate = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_candidate_001",
        email="jiwon@nunujal.com",
        name="최지원",
        student_id="20260004",
        department="산업디자인학과",
        profile_image_url="https://picsum.photos/seed/98765/200",
        status="ACTIVE",
        last_login_at=now - timedelta(hours=6),
    )
    user5 = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_member_002",
        email="front@nunujal.com",
        name="정프론트",
        student_id="20260005",
        department="소프트웨어학과",
        profile_image_url="https://picsum.photos/seed/front/200",
        status="ACTIVE",
        last_login_at=now - timedelta(hours=1),
    )
    user6 = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_member_003",
        email="back@nunujal.com",
        name="윤백엔드",
        student_id="20260006",
        department="컴퓨터공학과",
        profile_image_url="https://picsum.photos/seed/back/200",
        status="ACTIVE",
        last_login_at=now,
    )
    session.add_all([leader, member, reviewer, candidate, user5, user6])
    session.flush()

    project = models.Project(
        title="대학생 웹 서비스 공모전",
        description="서비스 고도화 및 DB 최적화 테스트를 위한 프로젝트",
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
            position_label="기획 및 팀장",
            memo="프로젝트 전반 관리",
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=member.id,
            project_role="MEMBER",
            position_label="데이터 분석",
            memo="DB 분석 및 통합",
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=reviewer.id,
            project_role="MEMBER",
            position_label="QA 및 문서화",
            memo="문서 및 코드 리뷰",
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=user5.id,
            project_role="MEMBER",
            position_label="프론트엔드 리드",
            memo="React UI 개발",
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=user6.id,
            project_role="MEMBER",
            position_label="백엔드/인프라",
            memo="서버 아키텍처 및 배포",
        ),
    ]
    session.add_all(project_members)
    session.flush()

    join_request = models.ProjectJoinRequest(
        project_id=project.id,
        requester_user_id=candidate.id,
        request_message="UI 디자인과 아이콘 리소스 정리를 맡고 싶습니다.",
        requested_position_label="디자이너",
        request_status="PENDING",
    )
    session.add(join_request)
    session.flush()

    work_item_1 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=user5.id,
        title="로그인 화면 UI 구현",
        description="구글 OAuth 연동을 포함한 랜딩 및 로그인 페이지 컴포넌트 구조화.",
        status="DONE",
        priority="HIGH",
        due_date=date(2026, 4, 10),
        started_at=now - timedelta(days=2),
        created_at=now - timedelta(days=3),
        gantt_sort_order=0,
    )
    work_item_2 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=reviewer.id,
        title="ORM 모델 구조 검토",
        description="다대다 테이블 확장 및 무결점 제약 사항 확인.",
        status="TODO",
        priority="MEDIUM",
        due_date=date(2026, 4, 15),
        started_at=now - timedelta(days=1),
        created_at=now - timedelta(days=2),
        gantt_sort_order=2,
    )
    work_item_3 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=user6.id,
        title="백엔드 로그인 API 개발",
        description="FastAPI 인증 관련 로직 처리 및 세션 관리.",
        status="IN_PROGRESS",
        priority="HIGH",
        due_date=date(2026, 4, 12),
        started_at=now - timedelta(days=1),
        created_at=now - timedelta(days=5),
        gantt_sort_order=1,
    )
    session.add_all([work_item_1, work_item_2, work_item_3])
    session.flush()

    session.add_all([
        models.WorkItemDependency(
            project_id=project.id,
            predecessor_work_item_id=work_item_1.id,
            successor_work_item_id=work_item_3.id,
        ),
        models.WorkItemDependency(
            project_id=project.id,
            predecessor_work_item_id=work_item_3.id,
            successor_work_item_id=work_item_2.id,
        ),
    ])
    session.flush()

    activity_1 = models.Activity(
        project_id=project.id,
        work_items=[work_item_1],
        actor_user_id=user5.id,
        activity_category="BASIC",
        activity_type="기능 개발",
        contribution_phase="DRAFTING",
        title="로그인 진입점 컴포넌트 작성",
        content="디자인 시스템을 반영한 버튼 영역 및 모달창 구현",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=1, hours=3),
        last_edited_by_user_id=user5.id,
        correction_reason="타이포그래피 여백 수정",
    )
    activity_2 = models.Activity(
        project_id=project.id,
        work_items=[work_item_3],
        actor_user_id=user5.id,
        target_user_id=user6.id,
        activity_category="PEER_SUPPORT",
        activity_type="디버깅",
        contribution_phase="SUPPORT",
        title="로그인 CORS 에러 해결 지원",
        content="프론트엔드쪽 로컬 포트 설정을 백엔드와 맞춰서 네트워크 통신 문제 방지 방안 안내",
        source_type="MANUAL",
        credibility_level="PEER_CONFIRMED",
        review_state="UNDER_REVIEW",
        occurred_at=now - timedelta(hours=10),
        last_edited_by_user_id=user5.id,
        correction_reason="지원 내용 보강",
    )
    activity_3 = models.Activity(
        project_id=project.id,
        work_items=[work_item_1, work_item_3],
        actor_user_id=leader.id,
        activity_category="BASIC",
        activity_type="테스트 및 리뷰",
        contribution_phase="REFINEMENT",
        title="로그인 플로우 통합 테스트 진행",
        content="회이트박스 및 블랙박스 통합 테스팅 로그 점검",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(hours=2),
        last_edited_by_user_id=leader.id,
    )
    activity_4 = models.Activity(
        project_id=project.id,
        work_items=[],
        actor_user_id=leader.id,
        activity_category="COMMON",
        activity_type="회의 진행",
        contribution_phase="PREPARATION",
        title="1주차 킥오프 전체 스프린트 회의",
        content="개발 템플릿 환경 공유 및 데이터베이스 ERD 구조 점검 회의",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=6),
        last_edited_by_user_id=leader.id,
    )
    session.add_all([activity_1, activity_2, activity_3, activity_4])
    session.flush()

    revision = models.ActivityRevisionHistory(
        activity_id=activity_2.id,
        edited_by_user_id=user5.id,
        previous_title="에러 해결",
        previous_content="CORS 에러 고쳤습니다.",
        previous_contribution_phase="SUPPORT",
        previous_credibility_level="SELF_REPORTED",
        previous_review_state="NORMAL",
        change_reason="상세 내역 추가 작성.",
    )
    session.add(revision)
    session.flush()

    analysis = models.AiAnalysis(
        project_id=project.id,
        requested_by_user_id=leader.id,
        analysis_start_date=date(2026, 3, 1),
        analysis_end_date=date(2026, 4, 3),
        model_name="gpt-5.4",
        prompt_version="v2",
        policy_version="v2",
        analysis_mode="DISPUTE_AWARE",
        snapshot_at=now,
        disputed_activity_count=1,
        low_credibility_activity_count=0,
        excluded_activity_count=0,
        status="COMPLETED",
        input_summary="팀원 전체 활동 내역을 기반으로 AI 기여도 분석이 실행되었습니다.",
        disclaimer="초기 더미 데이터 분석 결과입니다.",
        created_at=now - timedelta(hours=1),
        completed_at=now,
    )
    session.add(analysis)
    session.flush()

    contribution_result_1 = models.ContributionResult(
        analysis_id=analysis.id,
        target_user_id=user5.id,
        reference_score=Decimal("88.50"),
        confidence_score=Decimal("84.00"),
        result_status="NORMAL",
        execution_score=Decimal("90.00"),
        collaboration_score=Decimal("85.00"),
        documentation_score=Decimal("80.00"),
        problem_solving_score=Decimal("89.00"),
        disputed_activity_count=0,
        down_weighted_activity_count=0,
        summary="높은 프론트엔드 UI 구축 및 협업 기여.",
        rationale="할당된 작업을 완수하였고 타 팀원 인프라에 대한 유의미한 기술 지원을 수행하였습니다.",
        public_explanation="단독 태스크 및 원활한 팀원 지원 병행이 확인됨.",
        uncertainty_note="",
        warning_note="",
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
        summary="검토 작업 기여도 측정.",
        rationale="검토 진행 사항이 있으나 아직 대상자에 의해 승인되지 않은 지원 상태가 있습니다.",
        public_explanation="리뷰 단계의 지원이 부분적으로 반영되었습니다.",
        uncertainty_note="리뷰 상태의 활동 내역으로 신뢰도 감소.",
        warning_note="추가적인 확인이 필요합니다.",
    )
    session.add_all([contribution_result_1, contribution_result_2])
    session.flush()

    feedback_review_1 = models.FeedbackReview(
        project_id=project.id,
        author_user_id=leader.id,
        target_user_id=user5.id,
        activity_id=activity_1.id,
        request_type="SUPPLEMENT",
        visibility="LEADER_ONLY",
        requester_hidden_from_target=True,
        content="UI 구현체와 관련된 로직 히스토리를 더 명확히 기재해 주세요.",
        request_status="OPEN",
        ai_impact_mode="LOWER_CONFIDENCE_ONLY",
    )
    feedback_review_2 = models.FeedbackReview(
        project_id=project.id,
        author_user_id=user5.id,
        target_user_id=reviewer.id,
        contribution_result_id=contribution_result_2.id,
        request_type="RESULT_DISPUTE",
        visibility="LEADER_ONLY",
        requester_hidden_from_target=False,
        content="기여도 측정 시 반영된 리뷰 활동의 인정 수치가 다소 낮은 것 같습니다. 확인 부탁드립니다.",
        request_status="UNDER_REVIEW",
        ai_impact_mode="REQUIRE_REANALYSIS",
        reviewed_by_user_id=leader.id,
        created_at=now,
        reviewed_at=now,
        resolution_note="재분석 대기 중.",
    )
    session.add_all([feedback_review_1, feedback_review_2])
    session.flush()

    evidence_items = [
        models.Evidence(
            activity_id=activity_1.id,
            uploaded_by_user_id=user5.id,
            evidence_type="IMAGE",
            evidence_role="SUPPORTING",
            file_name="login-ui.png",
            resource_url="https://example.com/evidence/login-ui.png",
            description="로그인 UI 반영 결과 스크린샷 캡처본.",
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
            description="DB 검증 회의록 노션 링크.",
            verification_status="VERIFIED",
            captured_at=now - timedelta(hours=8),
        ),
    ]
    session.add_all(evidence_items)
    session.commit()

    return {
        "status": "created",
        "users": 6,
        "projects": 1,
        "project_join_requests": 1,
        "project_members": 5,
        "work_items": 3,
        "work_item_dependencies": 2,
        "activities": 4,
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
