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
    user7 = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_member_004",
        email="data@nunujal.com",
        name="강데이터",
        student_id="20260007",
        department="데이터사이언스학과",
        profile_image_url="https://picsum.photos/seed/data/200",
        status="ACTIVE",
        last_login_at=now - timedelta(hours=4),
    )
    user8 = models.AppUser(
        provider="GOOGLE",
        provider_user_id="dummy_google_member_005",
        email="plan@nunujal.com",
        name="문기획",
        student_id="20260008",
        department="경영정보학과",
        profile_image_url="https://picsum.photos/seed/plan/200",
        status="ACTIVE",
        last_login_at=now - timedelta(hours=8),
    )
    session.add_all([leader, member, reviewer, candidate, user5, user6, user7, user8])
    session.flush()

    project = models.Project(
        title="대학생 웹 서비스 공모전",
        description="서비스 고도화 및 DB 최적화 테스트를 위한 프로젝트",
        created_by_user_id=leader.id,
        join_code="TEAM42",
        join_code_active=True,
        join_policy="AUTO_APPROVE",
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
            user_id=candidate.id,
            project_role="MEMBER",
            position_label="UX/UI 디자인",
            memo="와이어프레임 및 디자인 시스템 정리",
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
        models.ProjectMember(
            project_id=project.id,
            user_id=user7.id,
            project_role="MEMBER",
            position_label="데이터 엔지니어링",
            memo="활동 데이터 요약 및 분석용 집계",
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=user8.id,
            project_role="MEMBER",
            position_label="서비스 기획",
            memo="사용자 시나리오와 발표 흐름 정리",
        ),
    ]
    session.add_all(project_members)
    session.flush()

    join_request = models.ProjectJoinRequest(
        project_id=project.id,
        requester_user_id=candidate.id,
        request_message="UI 디자인과 아이콘 리소스 정리를 맡고 싶습니다.",
        requested_position_label="디자이너",
        request_status="APPROVED",
        reviewed_by_user_id=leader.id,
        reviewed_project_role="MEMBER",
        reviewed_position_label="UX/UI 디자인",
        review_note="즉시 참여 정책으로 승인 처리된 더미 참여 이력입니다.",
        created_at=now - timedelta(days=13),
        updated_at=now - timedelta(days=12),
        reviewed_at=now - timedelta(days=12),
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
    work_item_4 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=user5.id,
        title="활동 필터 검색 UX 개선",
        description="작성자, 유형, 검토 상태, 할일 검색 조건을 사용자가 빠르게 조합할 수 있게 개선.",
        status="DONE",
        priority="MEDIUM",
        due_date=date(2026, 4, 18),
        started_at=now - timedelta(days=9),
        completed_at=now - timedelta(days=4),
        created_at=now - timedelta(days=10),
        gantt_sort_order=3,
    )
    work_item_5 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=leader.id,
        title="AI 기여도 산정 정책 초안",
        description="역할, 난이도, 품질, 협업을 고려한 상대 기여도 평가 정책 문서화.",
        status="IN_PROGRESS",
        priority="HIGH",
        due_date=date(2026, 4, 25),
        started_at=now - timedelta(days=6),
        created_at=now - timedelta(days=8),
        gantt_sort_order=4,
    )
    work_item_6 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=member.id,
        title="활동 데이터 모델 정규화",
        description="활동, 할일, 반응, 이의제기 데이터를 분석 가능한 형태로 정리.",
        status="DONE",
        priority="HIGH",
        due_date=date(2026, 4, 20),
        started_at=now - timedelta(days=8),
        completed_at=now - timedelta(days=2),
        created_at=now - timedelta(days=11),
        gantt_sort_order=5,
    )
    work_item_7 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=reviewer.id,
        title="QA 시나리오 및 회귀 테스트",
        description="핵심 플로우의 수동 테스트 시나리오와 재현 절차 정리.",
        status="IN_PROGRESS",
        priority="MEDIUM",
        due_date=date(2026, 4, 28),
        started_at=now - timedelta(days=5),
        created_at=now - timedelta(days=7),
        gantt_sort_order=6,
    )
    work_item_8 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=candidate.id,
        title="사용자 온보딩 와이어프레임",
        description="첫 방문 사용자의 프로젝트 참여, 활동 기록, 기여도 확인 흐름 와이어프레임.",
        status="DONE",
        priority="MEDIUM",
        due_date=date(2026, 4, 22),
        started_at=now - timedelta(days=7),
        completed_at=now - timedelta(days=1),
        created_at=now - timedelta(days=9),
        gantt_sort_order=7,
    )
    work_item_9 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=user7.id,
        title="활동 요약 집계 쿼리 설계",
        description="AI 입력 토큰 절감을 위한 활동 요약 기준과 집계 쿼리 초안 작성.",
        status="IN_PROGRESS",
        priority="HIGH",
        due_date=date(2026, 5, 3),
        started_at=now - timedelta(days=3),
        created_at=now - timedelta(days=4),
        gantt_sort_order=8,
    )
    work_item_10 = models.WorkItem(
        project_id=project.id,
        creator_user_id=leader.id,
        assignee_user_id=user8.id,
        title="발표 자료와 데모 플로우 정리",
        description="심사위원 관점에서 핵심 문제, 해결 방식, 데모 흐름을 발표 자료로 정리.",
        status="TODO",
        priority="LOW",
        due_date=date(2026, 5, 10),
        created_at=now - timedelta(days=2),
        gantt_sort_order=9,
    )
    session.add_all([
        work_item_1,
        work_item_2,
        work_item_3,
        work_item_4,
        work_item_5,
        work_item_6,
        work_item_7,
        work_item_8,
        work_item_9,
        work_item_10,
    ])
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
        models.WorkItemDependency(
            project_id=project.id,
            predecessor_work_item_id=work_item_6.id,
            successor_work_item_id=work_item_9.id,
        ),
        models.WorkItemDependency(
            project_id=project.id,
            predecessor_work_item_id=work_item_8.id,
            successor_work_item_id=work_item_10.id,
        ),
        models.WorkItemDependency(
            project_id=project.id,
            predecessor_work_item_id=work_item_4.id,
            successor_work_item_id=work_item_5.id,
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
    activity_5 = models.Activity(
        project_id=project.id,
        work_items=[work_item_8],
        actor_user_id=candidate.id,
        activity_category="BASIC",
        activity_type="UX 설계",
        contribution_phase="DRAFTING",
        title="온보딩 와이어프레임 1차 완성",
        content="프로젝트 참여, 활동 기록, 기여도 확인까지 이어지는 핵심 사용자 흐름을 화면 단위로 정리했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=5, hours=5),
        last_edited_by_user_id=candidate.id,
    )
    activity_6 = models.Activity(
        project_id=project.id,
        work_items=[work_item_6],
        actor_user_id=member.id,
        activity_category="BASIC",
        activity_type="데이터 모델링",
        contribution_phase="REFINEMENT",
        title="활동-할일 연결 구조 정규화 검토",
        content="활동과 할일의 다대다 관계를 기준으로 분석 가능한 테이블 구조와 조회 기준을 정리했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=4, hours=6),
        last_edited_by_user_id=member.id,
    )
    activity_7 = models.Activity(
        project_id=project.id,
        work_items=[work_item_3],
        actor_user_id=user6.id,
        activity_category="BASIC",
        activity_type="API 개발",
        contribution_phase="DRAFTING",
        title="로그인 세션 검증 API 구현",
        content="OAuth 로그인 이후 현재 사용자 정보를 반환하는 API와 세션 만료 처리 흐름을 구현했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=3, hours=7),
        last_edited_by_user_id=user6.id,
    )
    activity_8 = models.Activity(
        project_id=project.id,
        work_items=[work_item_7],
        actor_user_id=reviewer.id,
        activity_category="BASIC",
        activity_type="QA",
        contribution_phase="PREPARATION",
        title="핵심 플로우 회귀 테스트 체크리스트 작성",
        content="로그인, 프로젝트 참여, 할일 이동, 활동 기록, 활동 필터링에 대한 테스트 케이스를 정리했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=3, hours=1),
        last_edited_by_user_id=reviewer.id,
    )
    activity_9 = models.Activity(
        project_id=project.id,
        work_items=[work_item_9],
        actor_user_id=user7.id,
        activity_category="BASIC",
        activity_type="성능 개선",
        contribution_phase="DRAFTING",
        title="활동 요약용 집계 쿼리 초안 작성",
        content="AI 입력을 줄이기 위해 사용자별 활동 수, 연결 할일 수, 협업 활동 수를 요약하는 집계 기준을 설계했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=2, hours=9),
        last_edited_by_user_id=user7.id,
    )
    activity_10 = models.Activity(
        project_id=project.id,
        work_items=[work_item_5],
        actor_user_id=user8.id,
        target_user_id=leader.id,
        activity_category="PEER_SUPPORT",
        activity_type="정책 리뷰",
        contribution_phase="SUPPORT",
        title="기여도 정의 문구와 사용자 안내 문안 검토",
        content="기여도 정의가 팀원에게 과도한 평가처럼 보이지 않도록 설명 문구와 안내 플로우를 다듬었습니다.",
        source_type="MANUAL",
        credibility_level="PEER_CONFIRMED",
        review_state="RESOLVED",
        occurred_at=now - timedelta(days=2, hours=2),
        last_edited_by_user_id=user8.id,
    )
    activity_11 = models.Activity(
        project_id=project.id,
        work_items=[work_item_4, work_item_3],
        actor_user_id=user6.id,
        target_user_id=user5.id,
        activity_category="PEER_SUPPORT",
        activity_type="API 계약 조율",
        contribution_phase="SUPPORT",
        title="활동 필터 API 응답 형식 조율",
        content="프론트 필터 UI가 필요한 작성자, 할일, 페이지네이션 값을 안정적으로 받을 수 있게 응답 구조를 맞췄습니다.",
        source_type="MANUAL",
        credibility_level="PEER_CONFIRMED",
        review_state="NORMAL",
        occurred_at=now - timedelta(days=1, hours=18),
        last_edited_by_user_id=user6.id,
    )
    activity_12 = models.Activity(
        project_id=project.id,
        work_items=[work_item_9],
        actor_user_id=member.id,
        target_user_id=user7.id,
        activity_category="PEER_SUPPORT",
        activity_type="쿼리 리뷰",
        contribution_phase="REFINEMENT",
        title="활동 요약 쿼리의 중복 집계 위험 지적",
        content="활동-할일 다대다 연결 때문에 사용자별 집계가 중복될 수 있어 distinct 기준을 추가해야 한다고 리뷰했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="DISPUTED",
        occurred_at=now - timedelta(days=1, hours=12),
        last_edited_by_user_id=member.id,
    )
    activity_13 = models.Activity(
        project_id=project.id,
        work_items=[work_item_7],
        actor_user_id=reviewer.id,
        activity_category="BASIC",
        activity_type="버그 리포트",
        contribution_phase="REFINEMENT",
        title="활동 필터 초기화 후 할일 칩 잔존 버그 기록",
        content="필터 초기화 시 선택된 할일과 검색어가 함께 사라지는지 확인하는 회귀 테스트 항목을 추가했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(hours=22),
        last_edited_by_user_id=reviewer.id,
    )
    activity_14 = models.Activity(
        project_id=project.id,
        work_items=[work_item_8, work_item_10],
        actor_user_id=candidate.id,
        activity_category="COMMON",
        activity_type="디자인 시스템",
        contribution_phase="FINALIZATION",
        title="발표 데모용 화면 톤앤매너 정리",
        content="심사 자료에 들어갈 주요 화면의 버튼, 칩, 카드 스타일을 통일하고 데모 캡처 기준을 정리했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(hours=16),
        last_edited_by_user_id=candidate.id,
    )
    activity_15 = models.Activity(
        project_id=project.id,
        work_items=[],
        actor_user_id=leader.id,
        activity_category="COMMON",
        activity_type="일정 조율",
        contribution_phase="PREPARATION",
        title="중간 점검 회의에서 범위 재조정",
        content="AI 기여도 측정은 MVP 범위로 축소하고 활동 필터와 간트 안정화를 우선순위로 재배치했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(hours=9),
        last_edited_by_user_id=leader.id,
    )
    activity_16 = models.Activity(
        project_id=project.id,
        work_items=[work_item_4],
        actor_user_id=user5.id,
        activity_category="BASIC",
        activity_type="UX 개선",
        contribution_phase="FINALIZATION",
        title="할일 검색형 멀티 선택 필터 구현",
        content="할일 제목을 검색해 선택하면 칩으로 누적되고, 여러 할일을 OR 조건으로 조회할 수 있게 구현했습니다.",
        source_type="MANUAL",
        credibility_level="SELF_REPORTED",
        review_state="NORMAL",
        occurred_at=now - timedelta(hours=4),
        last_edited_by_user_id=user5.id,
    )
    session.add_all([
        activity_1,
        activity_2,
        activity_3,
        activity_4,
        activity_5,
        activity_6,
        activity_7,
        activity_8,
        activity_9,
        activity_10,
        activity_11,
        activity_12,
        activity_13,
        activity_14,
        activity_15,
        activity_16,
    ])
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
        analysis_end_date=date(2026, 5, 1),
        model_name="gemma4:26b",
        prompt_version="v2",
        policy_version="v2",
        analysis_mode="DISPUTE_AWARE",
        snapshot_at=now,
        disputed_activity_count=1,
        low_credibility_activity_count=0,
        excluded_activity_count=0,
        status="COMPLETED",
        input_summary="증거 자료는 제외하고 활동, 역할, 연결 할일, 협업 흐름, 열린 이의제기 내용을 요약하여 AI 기여도 분석이 실행되었습니다.",
        disclaimer="더미 데이터 기반 기여도 분석 결과이며 실제 평가는 모델과 프롬프트 설정에 따라 달라질 수 있습니다.",
        created_at=now - timedelta(hours=1),
        completed_at=now,
    )
    session.add(analysis)
    session.flush()

    contribution_results = [
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=leader.id,
            reference_score=Decimal("16.00"),
            confidence_score=Decimal("82.00"),
            result_status="NORMAL",
            execution_score=Decimal("14.00"),
            collaboration_score=Decimal("18.00"),
            documentation_score=Decimal("15.00"),
            problem_solving_score=Decimal("17.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="프로젝트 범위 조정과 기여도 정책 설계를 주도했습니다.",
            rationale="팀장 역할로 일정과 우선순위를 정리하고, AI 기여도 산정 정책의 기준을 구체화해 프로젝트 방향성에 기여했습니다.",
            public_explanation="일정 조율, 통합 테스트, 평가 정책 설계 기여를 반영했습니다.",
            uncertainty_note="일부 기획 활동은 결과물보다 조율 중심이라 직접 산출물 비중은 제한적으로 보았습니다.",
            warning_note="",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=member.id,
            reference_score=Decimal("12.00"),
            confidence_score=Decimal("78.00"),
            result_status="DISPUTED",
            execution_score=Decimal("12.00"),
            collaboration_score=Decimal("13.00"),
            documentation_score=Decimal("12.00"),
            problem_solving_score=Decimal("13.00"),
            disputed_activity_count=1,
            down_weighted_activity_count=0,
            summary="활동 데이터 모델과 집계 기준의 정확성 개선에 기여했습니다.",
            rationale="데이터 정규화와 중복 집계 위험 지적은 AI 평가 입력 품질에 직접 영향을 주는 기여로 보았습니다.",
            public_explanation="데이터 모델링과 쿼리 리뷰 활동을 반영했습니다.",
            uncertainty_note="쿼리 리뷰 활동 하나가 이의 상태라 최종 반영 정도는 재측정 시 조정될 수 있습니다.",
            warning_note="이의가 존재하는 활동을 포함합니다.",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=reviewer.id,
            reference_score=Decimal("10.00"),
            confidence_score=Decimal("76.00"),
            result_status="NORMAL",
            execution_score=Decimal("9.00"),
            collaboration_score=Decimal("10.00"),
            documentation_score=Decimal("13.00"),
            problem_solving_score=Decimal("9.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="QA 체크리스트와 회귀 테스트 항목 정리에 기여했습니다.",
            rationale="핵심 플로우 테스트 기준을 명확히 하여 안정성 검증 범위를 넓혔습니다.",
            public_explanation="QA 시나리오 작성과 버그 재현 기준 정리를 반영했습니다.",
            uncertainty_note="",
            warning_note="",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=candidate.id,
            reference_score=Decimal("12.00"),
            confidence_score=Decimal("79.00"),
            result_status="NORMAL",
            execution_score=Decimal("12.00"),
            collaboration_score=Decimal("11.00"),
            documentation_score=Decimal("12.00"),
            problem_solving_score=Decimal("11.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="온보딩 와이어프레임과 데모 화면 디자인 정리에 기여했습니다.",
            rationale="사용자가 프로젝트 참여부터 기여도 확인까지 이해할 수 있는 UX 흐름을 구체화했습니다.",
            public_explanation="UX 설계와 발표용 디자인 정리 활동을 반영했습니다.",
            uncertainty_note="",
            warning_note="",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=user5.id,
            reference_score=Decimal("15.00"),
            confidence_score=Decimal("84.00"),
            result_status="NORMAL",
            execution_score=Decimal("16.00"),
            collaboration_score=Decimal("14.00"),
            documentation_score=Decimal("12.00"),
            problem_solving_score=Decimal("15.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="프론트엔드 UI 구현과 활동 필터 UX 개선에 높은 기여를 했습니다.",
            rationale="로그인 UI, 활동 필터 검색형 멀티 선택, 백엔드 협업 요청 대응이 실제 사용성 향상에 연결되었습니다.",
            public_explanation="프론트엔드 구현과 필터 UX 개선 중심의 기여를 반영했습니다.",
            uncertainty_note="",
            warning_note="",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=user6.id,
            reference_score=Decimal("13.00"),
            confidence_score=Decimal("81.00"),
            result_status="NORMAL",
            execution_score=Decimal("14.00"),
            collaboration_score=Decimal("13.00"),
            documentation_score=Decimal("10.00"),
            problem_solving_score=Decimal("14.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="백엔드 로그인 API와 활동 필터 응답 계약 조율에 기여했습니다.",
            rationale="인증 API 구현과 프론트엔드가 사용할 응답 구조 조율이 기능 완성도에 영향을 주었습니다.",
            public_explanation="백엔드 구현과 API 계약 협업을 반영했습니다.",
            uncertainty_note="",
            warning_note="",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=user7.id,
            reference_score=Decimal("11.00"),
            confidence_score=Decimal("74.00"),
            result_status="UNDER_REVIEW",
            execution_score=Decimal("11.00"),
            collaboration_score=Decimal("10.00"),
            documentation_score=Decimal("11.00"),
            problem_solving_score=Decimal("12.00"),
            disputed_activity_count=1,
            down_weighted_activity_count=0,
            summary="AI 입력 토큰 절감을 위한 활동 요약 집계 기준을 설계했습니다.",
            rationale="활동 요약 집계는 향후 기여도 평가의 확장성에 기여하지만, 일부 쿼리 기준은 리뷰 중입니다.",
            public_explanation="활동 요약 집계 설계와 데이터 분석 기반 기여를 반영했습니다.",
            uncertainty_note="중복 집계 관련 이의가 있어 재검토 여지가 있습니다.",
            warning_note="이의제기 대상과 연결된 활동이 있습니다.",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=user8.id,
            reference_score=Decimal("11.00"),
            confidence_score=Decimal("77.00"),
            result_status="NORMAL",
            execution_score=Decimal("10.00"),
            collaboration_score=Decimal("12.00"),
            documentation_score=Decimal("12.00"),
            problem_solving_score=Decimal("10.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="서비스 설명 문안과 발표 흐름 정리에 기여했습니다.",
            rationale="기여도 정책의 사용자 이해도를 높이고 데모 흐름을 심사 관점으로 정리했습니다.",
            public_explanation="기획 문안, 정책 리뷰, 발표 흐름 정리를 반영했습니다.",
            uncertainty_note="",
            warning_note="",
        ),
    ]
    session.add_all(contribution_results)
    session.flush()
    contribution_result_by_user_id = {result.target_user_id: result for result in contribution_results}

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
        contribution_result_id=contribution_result_by_user_id[reviewer.id].id,
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
    feedback_review_3 = models.FeedbackReview(
        project_id=project.id,
        author_user_id=user7.id,
        target_user_id=member.id,
        contribution_result_id=contribution_result_by_user_id[member.id].id,
        request_type="RESULT_DISPUTE",
        visibility="LEADER_ONLY",
        requester_hidden_from_target=False,
        content="중복 집계 위험을 지적받은 부분은 맞지만, 요약 쿼리 초안 자체의 기여가 과소평가되지는 않았는지 재검토가 필요합니다.",
        request_status="OPEN",
        ai_impact_mode="REQUIRE_REANALYSIS",
        created_at=now - timedelta(hours=3),
    )
    feedback_review_4 = models.FeedbackReview(
        project_id=project.id,
        author_user_id=user8.id,
        target_user_id=candidate.id,
        activity_id=activity_14.id,
        request_type="SUPPLEMENT",
        visibility="LEADER_ONLY",
        requester_hidden_from_target=True,
        content="발표 데모 화면 정리 활동에 사용자 흐름 검토도 함께 포함되었으니 설명을 보강하면 좋겠습니다.",
        request_status="OPEN",
        ai_impact_mode="LOWER_CONFIDENCE_ONLY",
        created_at=now - timedelta(hours=2),
    )
    session.add_all([feedback_review_1, feedback_review_2, feedback_review_3, feedback_review_4])
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
        "users": 8,
        "projects": 1,
        "project_join_requests": 1,
        "project_members": 8,
        "work_items": 10,
        "work_item_dependencies": 5,
        "activities": 16,
        "activity_revisions": 1,
        "ai_analyses": 1,
        "contribution_results": 8,
        "feedback_reviews": 4,
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
