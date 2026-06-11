from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException
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


def insert_dummy_data(session: Session, *, reset_existing: bool = False) -> dict[str, int | str]:
    now = datetime.now()
    project_start = date.today() - timedelta(days=53)
    project_end = project_start + timedelta(days=90)
    project_start_at = datetime(project_start.year, project_start.month, project_start.day, 9, 0, 0)

    existing_projects = session.query(models.Project).filter(models.Project.join_code == "TEAM42").all()
    if existing_projects and not reset_existing:
        return {
            "status": "skipped",
            "message": "Dummy project already exists. Seed API did not modify existing data.",
            "projects": len(existing_projects),
        }
    for existing_project in existing_projects:
        session.delete(existing_project)
    session.flush()

    def upsert_dummy_user(
        *,
        provider_user_id: str,
        email: str,
        name: str,
        student_id: str,
        department: str,
        profile_image_url: str,
        last_login_at: datetime,
    ) -> models.AppUser:
        user = (
            session.query(models.AppUser)
            .filter(
                models.AppUser.provider == "GOOGLE",
                models.AppUser.provider_user_id == provider_user_id,
            )
            .first()
        )
        if user is None:
            user = models.AppUser(provider="GOOGLE", provider_user_id=provider_user_id)
            session.add(user)

        user.email = email
        user.name = name
        user.student_id = student_id
        user.department = department
        user.profile_image_url = profile_image_url
        user.status = "ACTIVE"
        user.last_login_at = last_login_at
        return user

    leader = upsert_dummy_user(
        provider_user_id="dummy_google_leader_001",
        email="nunu@nunujal.com",
        name="김누누",
        student_id="20260001",
        department="컴퓨터공학과",
        profile_image_url="https://picsum.photos/seed/nunu-lead/200",
        last_login_at=now,
    )
    frontend = upsert_dummy_user(
        provider_user_id="dummy_google_member_001",
        email="seojun@nunujal.com",
        name="한서준",
        student_id="20260002",
        department="소프트웨어학과",
        profile_image_url="https://picsum.photos/seed/han-seojun/200",
        last_login_at=now - timedelta(minutes=25),
    )
    backend = upsert_dummy_user(
        provider_user_id="dummy_google_reviewer_001",
        email="harin@nunujal.com",
        name="유하린",
        student_id="20260003",
        department="컴퓨터공학과",
        profile_image_url="https://picsum.photos/seed/yoo-harin/200",
        last_login_at=now - timedelta(hours=1),
    )
    designer = upsert_dummy_user(
        provider_user_id="dummy_google_candidate_001",
        email="jimin@nunujal.com",
        name="오지민",
        student_id="20260004",
        department="산업디자인학과",
        profile_image_url="https://picsum.photos/seed/oh-jimin/200",
        last_login_at=now - timedelta(hours=3),
    )
    users = [leader, frontend, backend, designer]
    session.add_all(users)
    session.flush()

    project = models.Project(
        title="누누잘 개발 프로젝트",
        description="팀 프로젝트의 할일, 활동, 채팅, AI 기여도 산정을 하나의 흐름으로 관리하는 협업 플랫폼 개발 프로젝트입니다.",
        created_by_user_id=leader.id,
        join_code="TEAM42",
        join_code_active=True,
        join_policy="AUTO_APPROVE",
        join_code_created_at=project_start_at,
        join_code_expires_at=project_start_at + timedelta(days=90),
        start_date=project_start,
        end_date=project_end,
        status="IN_PROGRESS",
        created_at=project_start_at,
        updated_at=now,
    )
    session.add(project)
    session.flush()

    project_members = [
        models.ProjectMember(
            project_id=project.id,
            user_id=leader.id,
            project_role="LEADER",
            position_label="프로젝트 리드",
            memo="기획, 정책, 일정 조율과 최종 품질 관리를 담당합니다.",
            joined_at=project_start_at,
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=frontend.id,
            project_role="MEMBER",
            position_label="프론트엔드",
            memo="React 화면, 간트차트, 활동/채팅 UX 구현을 담당합니다.",
            joined_at=project_start_at + timedelta(days=1),
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=backend.id,
            project_role="MEMBER",
            position_label="백엔드/인프라",
            memo="FastAPI, DB 모델, 인증, 파일 저장, AI 연동을 담당합니다.",
            joined_at=project_start_at + timedelta(days=1),
        ),
        models.ProjectMember(
            project_id=project.id,
            user_id=designer.id,
            project_role="MEMBER",
            position_label="UX/UI 디자인",
            memo="사용자 흐름, 화면 구조, 데모 캡처 품질을 담당합니다.",
            joined_at=project_start_at + timedelta(days=2),
        ),
    ]
    session.add_all(project_members)
    session.flush()

    join_requests = [
        models.ProjectJoinRequest(
            project_id=project.id,
            requester_user_id=frontend.id,
            request_message="프론트엔드 화면 구현과 사용성 개선을 맡겠습니다.",
            requested_position_label="프론트엔드",
            request_status="APPROVED",
            reviewed_by_user_id=leader.id,
            reviewed_project_role="MEMBER",
            reviewed_position_label="프론트엔드",
            review_note="즉시 참여 정책으로 승인 처리된 참여 이력입니다.",
            created_at=project_start_at + timedelta(days=1, hours=1),
            updated_at=project_start_at + timedelta(days=1, hours=1, minutes=5),
            reviewed_at=project_start_at + timedelta(days=1, hours=1, minutes=5),
        ),
        models.ProjectJoinRequest(
            project_id=project.id,
            requester_user_id=backend.id,
            request_message="백엔드 API와 배포 구조를 담당하겠습니다.",
            requested_position_label="백엔드/인프라",
            request_status="APPROVED",
            reviewed_by_user_id=leader.id,
            reviewed_project_role="MEMBER",
            reviewed_position_label="백엔드/인프라",
            review_note="즉시 참여 정책으로 승인 처리된 참여 이력입니다.",
            created_at=project_start_at + timedelta(days=1, hours=2),
            updated_at=project_start_at + timedelta(days=1, hours=2, minutes=5),
            reviewed_at=project_start_at + timedelta(days=1, hours=2, minutes=5),
        ),
        models.ProjectJoinRequest(
            project_id=project.id,
            requester_user_id=designer.id,
            request_message="온보딩과 주요 화면 UX 설계를 담당하겠습니다.",
            requested_position_label="UX/UI 디자인",
            request_status="APPROVED",
            reviewed_by_user_id=leader.id,
            reviewed_project_role="MEMBER",
            reviewed_position_label="UX/UI 디자인",
            review_note="즉시 참여 정책으로 승인 처리된 참여 이력입니다.",
            created_at=project_start_at + timedelta(days=2, hours=1),
            updated_at=project_start_at + timedelta(days=2, hours=1, minutes=5),
            reviewed_at=project_start_at + timedelta(days=2, hours=1, minutes=5),
        ),
    ]
    session.add_all(join_requests)
    session.flush()

    user_by_key = {
        "lead": leader,
        "front": frontend,
        "back": backend,
        "design": designer,
    }

    def at(day: int, hour: int = 10, minute: int = 0) -> datetime:
        return project_start_at + timedelta(days=day, hours=hour - 9, minutes=minute)

    def day(day: int) -> date:
        return project_start + timedelta(days=day)

    def make_work_item(
        key: str,
        title: str,
        description: str,
        assignee_key: str,
        status: str,
        priority: str,
        start_day: int,
        end_day: int,
        sort_order: int,
        parent_key: str | None = None,
    ) -> models.WorkItem:
        start_at = at(start_day, 9)
        completed_at = at(end_day, 18) if status == "DONE" else None
        item = models.WorkItem(
            project_id=project.id,
            creator_user_id=leader.id,
            assignee_user_id=user_by_key[assignee_key].id,
            parent_work_item_id=work_items_by_key[parent_key].id if parent_key else None,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=day(end_day),
            started_at=start_at if status != "TODO" else None,
            completed_at=completed_at,
            created_at=at(max(start_day - 2, 0), 9),
            updated_at=completed_at or at(min(end_day, 44), 17),
            gantt_sort_order=sort_order,
        )
        session.add(item)
        session.flush()
        work_items_by_key[key] = item
        return item

    work_items_by_key: dict[str, models.WorkItem] = {}
    order = 0
    phase_specs = [
        ("phase_planning", "1. 기획/정책 설계", "누누잘의 핵심 문제 정의, 사용자 흐름, 기여도 정책을 정리합니다.", "lead", "DONE", "HIGH", 0, 14),
        ("phase_foundation", "2. 인증/프로젝트 기반", "로그인, 세션, 프로젝트 생성/참여, 기본 API를 구축합니다.", "back", "DONE", "HIGH", 5, 24),
        ("phase_workflow", "3. 할일/활동 관리", "칸반, 간트, 활동 기록, 필터, 증거 첨부를 연결합니다.", "front", "IN_PROGRESS", "HIGH", 15, 47),
        ("phase_ai", "4. AI 기여도/이의제기", "활동 요약과 AI 산정, 이의제기 재평가 흐름을 구현합니다.", "lead", "IN_PROGRESS", "HIGH", 25, 57),
        ("phase_realtime", "5. 실시간 채팅/파일", "프로젝트 그룹 채팅, 읽음 처리, 파일/이미지 첨부를 구현합니다.", "back", "IN_PROGRESS", "MEDIUM", 36, 62),
        ("phase_demo", "6. 품질 안정화/데모", "반응형, 회귀 테스트, 발표 시나리오와 데모 데이터를 정리합니다.", "design", "TODO", "MEDIUM", 50, 84),
    ]
    for spec in phase_specs:
        make_work_item(*spec, sort_order=order)
        order += 1

    child_specs = [
        ("research_user_flow", "핵심 사용자 흐름과 문제 정의", "프로젝트 생성부터 기여도 확인까지 사용자가 자연스럽게 이해할 수 있는 흐름을 정의합니다.", "lead", "DONE", "HIGH", 1, 5, "phase_planning"),
        ("wireframe_onboarding", "온보딩/프로젝트 선택 와이어프레임", "프로젝트 선택, 참여 코드 입력, 내 정보 진입 흐름의 저충실도 와이어프레임을 작성합니다.", "design", "DONE", "MEDIUM", 3, 9, "phase_planning"),
        ("contribution_policy", "기여도 산정 정책 초안", "역할, 난이도, 품질, 협업을 고려한 기여도 정의와 사용자 안내 문구를 정리합니다.", "lead", "DONE", "HIGH", 7, 14, "phase_planning"),
        ("data_schema", "DB 모델과 마이그레이션 기준 정리", "프로젝트, 멤버, 할일, 활동, 증거, 기여도 테이블 관계를 정리합니다.", "back", "DONE", "HIGH", 6, 13, "phase_foundation"),
        ("auth_session", "구글 로그인과 세션 유지 구현", "OAuth 로그인, refresh token, 단일 세션 정책, 로그아웃 처리를 구현합니다.", "back", "DONE", "HIGH", 10, 20, "phase_foundation"),
        ("project_join", "프로젝트 생성/참여 코드 플로우", "즉시 참여와 승인 요청 흐름을 분리하고 프로젝트 선택 화면으로 복귀하는 UX를 구현합니다.", "front", "DONE", "MEDIUM", 14, 23, "phase_foundation"),
        ("kanban_board", "할일 칸반보드 CRUD", "상태별 할일 카드, 수정 오버레이, 완료 전 확인 흐름을 구현합니다.", "front", "DONE", "HIGH", 16, 28, "phase_workflow"),
        ("gantt_hierarchy", "간트차트 계층형 일정 관리", "할일 parent/child 저장, 드래그 정렬, 의존성 라인, 전체화면을 구현합니다.", "front", "IN_PROGRESS", "HIGH", 20, 43, "phase_workflow"),
        ("activity_log", "활동 기록과 팀원 지원 플로우", "내 할일, 팀원 지원, 공통 활동 기록과 검토 상태를 연결합니다.", "back", "DONE", "HIGH", 21, 33, "phase_workflow"),
        ("activity_filter", "활동 필터와 할일 검색 UX", "작성자, 유형, 검토 상태, 기간, 할일 검색 조건을 조합할 수 있게 구현합니다.", "front", "DONE", "MEDIUM", 29, 40, "phase_workflow"),
        ("activity_evidence", "활동 증거 파일 첨부", "S3 presigned upload와 이미지 미리보기, 다운로드 링크를 활동 기록에 연결합니다.", "back", "IN_PROGRESS", "HIGH", 34, 47, "phase_workflow"),
        ("ai_prompt", "AI 기여도 프롬프트 설계", "기본 측정과 이의제기 측정에 들어갈 입력 구조와 출력 JSON 형식을 설계합니다.", "lead", "DONE", "HIGH", 25, 35, "phase_ai"),
        ("ai_provider", "Gemini API 기여도 측정 연동", "모델 provider를 교체 가능하게 만들고 Gemini 2.5 Flash 연동을 구성합니다.", "back", "IN_PROGRESS", "HIGH", 33, 51, "phase_ai"),
        ("objection_queue", "이의제기 재측정 큐", "기여도 측정 중 추가 요청은 큐에 쌓고 완료 후 순차 처리합니다.", "back", "IN_PROGRESS", "HIGH", 38, 55, "phase_ai"),
        ("contribution_ui", "기여도 파이차트 UI 개선", "팀원별 파이를 클릭하면 상세 근거와 이의 내역을 확인할 수 있게 개선합니다.", "front", "IN_PROGRESS", "MEDIUM", 40, 57, "phase_ai"),
        ("chat_group", "프로젝트 그룹 채팅", "프로젝트별 기본 그룹 채팅방, WebSocket 실시간 메시지, 읽음 처리 구조를 구현합니다.", "back", "IN_PROGRESS", "MEDIUM", 36, 50, "phase_realtime"),
        ("chat_files", "채팅 파일/이미지 첨부", "채팅 첨부파일 5일 보관, 이미지 미리보기, 만료 표시를 구현합니다.", "front", "TODO", "MEDIUM", 49, 62, "phase_realtime"),
        ("responsive_workspace", "작은 화면 워크스페이스 대응", "좁은 화면에서 사이드바와 간트 툴바가 겹치지 않도록 반응형 레이아웃을 정리합니다.", "front", "IN_PROGRESS", "MEDIUM", 44, 58, "phase_demo"),
        ("qa_regression", "핵심 플로우 회귀 테스트", "로그인, 프로젝트 참여, 할일 이동, 활동 등록, 기여도 측정, 채팅을 테스트합니다.", "lead", "TODO", "HIGH", 58, 76, "phase_demo"),
        ("demo_script", "발표 자료와 데모 시나리오", "심사위원에게 보여줄 문제 정의, 화면 흐름, 데모 계정을 정리합니다.", "design", "TODO", "LOW", 64, 84, "phase_demo"),
    ]
    for spec in child_specs:
        make_work_item(
            key=spec[0],
            title=spec[1],
            description=spec[2],
            assignee_key=spec[3],
            status=spec[4],
            priority=spec[5],
            start_day=spec[6],
            end_day=spec[7],
            sort_order=order,
            parent_key=spec[8],
        )
        order += 1

    dependency_pairs = [
        ("research_user_flow", "wireframe_onboarding"),
        ("research_user_flow", "contribution_policy"),
        ("data_schema", "auth_session"),
        ("auth_session", "project_join"),
        ("project_join", "kanban_board"),
        ("kanban_board", "gantt_hierarchy"),
        ("activity_log", "activity_filter"),
        ("activity_log", "activity_evidence"),
        ("activity_filter", "ai_prompt"),
        ("ai_prompt", "ai_provider"),
        ("ai_provider", "objection_queue"),
        ("objection_queue", "contribution_ui"),
        ("auth_session", "chat_group"),
        ("activity_evidence", "chat_files"),
        ("gantt_hierarchy", "responsive_workspace"),
        ("responsive_workspace", "qa_regression"),
        ("qa_regression", "demo_script"),
    ]
    session.add_all([
        models.WorkItemDependency(
            project_id=project.id,
            predecessor_work_item_id=work_items_by_key[source].id,
            successor_work_item_id=work_items_by_key[target].id,
        )
        for source, target in dependency_pairs
    ])
    session.flush()

    def make_activity(
        key: str,
        actor_key: str,
        title: str,
        content: str,
        item_keys: list[str],
        offset_day: int,
        category: str = "BASIC",
        activity_type: str = "기능 개발",
        phase: str = "DRAFTING",
        target_key: str | None = None,
        review_state: str = "NORMAL",
        credibility: str = "SELF_REPORTED",
        hour: int = 10,
    ) -> models.Activity:
        activity = models.Activity(
            project_id=project.id,
            work_items=[work_items_by_key[item_key] for item_key in item_keys],
            actor_user_id=user_by_key[actor_key].id,
            target_user_id=user_by_key[target_key].id if target_key else None,
            activity_category=category,
            activity_type=activity_type,
            contribution_phase=phase,
            title=title,
            content=content,
            source_type="MANUAL",
            credibility_level=credibility,
            review_state=review_state,
            occurred_at=at(offset_day, hour),
            created_at=at(offset_day, hour, 5),
            updated_at=at(offset_day, hour, 20),
            last_edited_by_user_id=user_by_key[actor_key].id,
        )
        session.add(activity)
        session.flush()
        activities_by_key[key] = activity
        return activity

    activities_by_key: dict[str, models.Activity] = {}
    activity_specs = [
        ("a01", "lead", "문제 정의와 MVP 범위 확정", "팀 프로젝트 기여도를 활동 기반으로 설명하는 문제 정의와 1차 MVP 범위를 문서로 정리했습니다.", ["research_user_flow"], 1, "COMMON", "기획", "PREPARATION", None, "NORMAL", "SELF_REPORTED", 10),
        ("a02", "design", "프로젝트 선택 화면 사용자 흐름 초안", "프로젝트가 여러 개일 때 선택, 참여, 내 정보 진입이 헷갈리지 않도록 와이어프레임을 작성했습니다.", ["wireframe_onboarding"], 3, "BASIC", "UX 설계", "PREPARATION", None, "NORMAL", "SELF_REPORTED", 14),
        ("a03", "back", "핵심 테이블 관계 초안 작성", "프로젝트, 멤버, 할일, 활동, 증거, 기여도 결과 간 관계를 ERD 기준으로 정리했습니다.", ["data_schema"], 6, "BASIC", "DB 설계", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 11),
        ("a04", "lead", "기여도 정의 문구 작성", "기여도를 프로젝트 목표 달성에 기여한 상대적 지분으로 설명하는 안내 문구를 작성했습니다.", ["contribution_policy"], 8, "BASIC", "정책 설계", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 15),
        ("a05", "front", "로그인 페이지 기본 레이아웃 구현", "로고, 프로필 진입, 프로젝트 선택 플로우와 연결되는 로그인 화면 구조를 만들었습니다.", ["project_join"], 12, "BASIC", "UI 구현", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 10),
        ("a06", "back", "OAuth 콜백과 세션 발급 구현", "구글 로그인 이후 access token과 refresh token을 발급하고 쿠키에 저장하는 흐름을 구현했습니다.", ["auth_session"], 13, "BASIC", "인증", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 13),
        ("a07", "front", "프로젝트 생성 후 목록 복귀 UX 반영", "프로젝트 생성 직후 상세로 바로 이동하지 않고 생성 완료를 알린 뒤 프로젝트 선택 화면으로 돌아오게 수정했습니다.", ["project_join"], 16, "BASIC", "UX 개선", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 17),
        ("a08", "back", "프로젝트 참여 코드 즉시 참여 처리", "AUTO_APPROVE 프로젝트는 참여 요청과 동시에 멤버십이 생성되도록 API 흐름을 정리했습니다.", ["project_join"], 17, "BASIC", "API 개발", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 10),
        ("a09", "lead", "1차 스프린트 리뷰 진행", "인증, 프로젝트 생성, 참여 코드 흐름을 기준으로 남은 범위와 우선순위를 재정렬했습니다.", [], 18, "COMMON", "회의", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 15),
        ("a10", "front", "칸반 카드 상태 이동 구현", "TODO, 진행 중, 완료 컬럼 간 드래그 이동과 완료 전 확인 흐름을 구현했습니다.", ["kanban_board"], 21, "BASIC", "기능 개발", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 11),
        ("a11", "back", "할일 생성/수정 API 일정 필드 정리", "간트차트와 칸반보드가 같은 일정 데이터를 쓰도록 timeline_start_date와 timeline_end_date를 정리했습니다.", ["kanban_board", "gantt_hierarchy"], 22, "PEER_SUPPORT", "API 계약", "SUPPORT", "front", "RESOLVED", "PEER_CONFIRMED", 14),
        ("a12", "design", "할일 카드 정보 밀도 리뷰", "카드에 항상 보여줄 정보와 더보기에서 보여줄 첨부 결과물을 구분하는 사용성 리뷰를 작성했습니다.", ["kanban_board"], 23, "PEER_SUPPORT", "UX 리뷰", "SUPPORT", "front", "RESOLVED", "PEER_CONFIRMED", 16),
        ("a13", "front", "활동 등록 오버레이 1차 구현", "대상 할일 선택, 활동 내용, 성격 태그, 증거 자료 입력 영역을 한 흐름으로 구성했습니다.", ["activity_log"], 24, "BASIC", "UI 구현", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 10),
        ("a14", "back", "활동과 할일 다대다 연결 저장", "활동 하나가 여러 할일에 연결될 수 있도록 링크 테이블 저장과 조회 직렬화를 구현했습니다.", ["activity_log", "data_schema"], 25, "BASIC", "DB 구현", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 13),
        ("a15", "lead", "활동 유형 기준 정리", "내 할일, 팀원 지원, 공통 작업의 의미를 분리하고 팀원 페이지에서 함께 보이도록 기준을 정리했습니다.", ["activity_log", "contribution_policy"], 26, "BASIC", "정책 설계", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 16),
        ("a16", "front", "활동 필터 작성자/상태 조건 구현", "작성자, 유형, 검토 상태, 기간 조건을 조합해 활동 목록을 좁힐 수 있게 구현했습니다.", ["activity_filter"], 29, "BASIC", "필터 구현", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 11),
        ("a17", "back", "활동 필터 API 조건 정리", "q, category, review_state, work_item_ids, filter_operator 조건을 백엔드 쿼리로 연결했습니다.", ["activity_filter"], 30, "BASIC", "API 개발", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 14),
        ("a18", "front", "할일 검색 드롭다운 UX 개선", "활동 필터에서 할일 제목을 입력하면 실시간 검색 결과가 뜨고 선택하면 칩으로 누적되게 개선했습니다.", ["activity_filter"], 31, "BASIC", "UX 개선", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 10),
        ("a19", "design", "활동 필터 화면 복잡도 리뷰", "필터 조건이 과하게 많아 보이는 문제를 짚고 자주 쓰는 조건만 남기는 방향을 제안했습니다.", ["activity_filter"], 31, "PEER_SUPPORT", "UX 리뷰", "SUPPORT", "front", "RESOLVED", "PEER_CONFIRMED", 15),
        ("a20", "front", "간트차트 기본 렌더링 적용", "DHTMLX Gantt를 프로젝트 개요에 연결하고 할일 상태별 색상과 날짜 헤더를 적용했습니다.", ["gantt_hierarchy"], 33, "BASIC", "간트차트", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 11),
        ("a21", "back", "간트 계층 저장 컬럼 추가", "parent_work_item_id와 gantt_sort_order를 DB와 모델에 추가하고 계층 저장 API를 구현했습니다.", ["gantt_hierarchy", "data_schema"], 34, "BASIC", "DB 구현", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 13),
        ("a22", "front", "간트 계층 드래그 저장 연결", "할일을 부모/자식으로 드래그하면 계층과 정렬 순서가 서버에 저장되도록 연결했습니다.", ["gantt_hierarchy"], 35, "BASIC", "간트차트", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 10),
        ("a23", "front", "간트 날짜 셀 깜빡임 원인 기록", "접기/펼치기와 드래그 시 날짜 영역이 재렌더링되며 흰 화면이 생기는 현상을 재현했습니다.", ["gantt_hierarchy", "qa_regression"], 36, "BASIC", "버그 리포트", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 16),
        ("a24", "back", "S3 업로드 presigned URL API 구현", "프로젝트 파일 첨부를 위해 업로드 URL 발급, 파일 메타데이터 저장, 삭제 API를 구현했습니다.", ["activity_evidence"], 36, "BASIC", "파일 업로드", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 11),
        ("a25", "front", "활동 이미지 미리보기 모달 개선", "활동 페이지에서 이미지가 잘리지 않도록 모달 크기와 object-fit 처리를 조정했습니다.", ["activity_evidence"], 37, "BASIC", "UI 개선", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 14),
        ("a26", "lead", "AI 입력 정보 범위 정리", "기본 측정과 이의제기 시 AI에게 전달할 활동, 할일, 기존 판단 근거 범위를 문서화했습니다.", ["ai_prompt"], 38, "BASIC", "AI 정책", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 15),
        ("a27", "back", "기여도 분석 스냅샷 생성기 작성", "팀원, 활동 요약, 변경 활동, 관련 할일을 JSON으로 직렬화하는 스냅샷 생성 로직을 구현했습니다.", ["ai_provider", "ai_prompt"], 39, "BASIC", "AI 연동", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 10),
        ("a28", "front", "기여도 파이차트 선택 인터랙션 구현", "파이를 클릭하면 해당 팀원의 기여도 근거가 오른쪽에 보이도록 UI를 개선했습니다.", ["contribution_ui"], 40, "BASIC", "UI 구현", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 12),
        ("a29", "design", "기여도 페이지 정보 구조 리뷰", "내 기여도와 팀원별 상세가 중복 노출되던 문제를 정리하고 파이차트 중심 구조를 제안했습니다.", ["contribution_ui"], 40, "PEER_SUPPORT", "UX 리뷰", "SUPPORT", "front", "RESOLVED", "PEER_CONFIRMED", 16),
        ("a30", "back", "Gemini provider 추가", "로컬 Ollama provider와 분리해 Gemini API provider를 추가하고 모델 설정을 교체 가능하게 만들었습니다.", ["ai_provider"], 41, "BASIC", "AI 연동", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 11),
        ("a31", "back", "기여도 재측정 큐 처리", "측정 중 추가 요청과 이의제기 요청이 순서대로 처리되도록 큐와 이벤트 브로드캐스트를 정리했습니다.", ["objection_queue"], 42, "BASIC", "비동기 처리", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 13),
        ("a32", "lead", "이의제기 UX 정책 확정", "본인이 제기한 이의와 자신에게 온 이의를 구분해 볼 수 있도록 권한 기준을 정리했습니다.", ["objection_queue", "contribution_ui"], 42, "COMMON", "정책 회의", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 17),
        ("a33", "front", "기여도 이의제기 버튼 상태 처리", "이미 해당 팀원에 대한 이의가 처리 중이면 버튼을 비활성화하고 안내 문구를 표시했습니다.", ["contribution_ui", "objection_queue"], 43, "BASIC", "UX 개선", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 10),
        ("a34", "back", "프로젝트 그룹 채팅방 자동 동기화", "프로젝트 멤버가 바뀌면 그룹 채팅 멤버십도 함께 맞춰지도록 동기화 로직을 구현했습니다.", ["chat_group"], 43, "BASIC", "채팅", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 14),
        ("a35", "front", "채팅 위젯 기본 UI 연결", "우측 하단 채팅 버튼, 채팅방 목록, 메시지 패널, 미확인 배지를 구현했습니다.", ["chat_group"], 44, "BASIC", "채팅 UI", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 11),
        ("a36", "back", "채팅 읽음 카운트 계산", "메시지별 안 읽은 사람 수와 방별 미확인 메시지 수를 계산하는 API를 추가했습니다.", ["chat_group"], 44, "PEER_SUPPORT", "API 계약", "SUPPORT", "front", "UNDER_REVIEW", "PEER_CONFIRMED", 16),
        ("a37", "front", "채팅창 크기 조절 핸들 구현", "최소 크기를 유지하면서 사용자가 채팅 패널 크기를 늘릴 수 있게 했습니다.", ["chat_group"], 45, "BASIC", "채팅 UI", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 10),
        ("a38", "back", "WebSocket 세션 재검증 추가", "세션 revoke 이후에도 실시간 연결이 살아있는 문제를 막기 위해 루프 중 세션 상태를 재확인했습니다.", ["auth_session", "chat_group"], 45, "BASIC", "보안 개선", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 13),
        ("a39", "front", "워크스페이스 작은 화면 대응", "좁은 화면에서 사이드바가 텍스트와 겹치지 않도록 가로 아이콘 탭으로 전환했습니다.", ["responsive_workspace"], 46, "BASIC", "반응형", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 11),
        ("a40", "design", "모바일 레이아웃 캡처 리뷰", "작은 화면 캡처 기준으로 헤더, 메뉴, 간트 툴바의 정보 밀도와 여백을 점검했습니다.", ["responsive_workspace"], 46, "PEER_SUPPORT", "디자인 리뷰", "SUPPORT", "front", "RESOLVED", "PEER_CONFIRMED", 15),
        ("a41", "lead", "중간 점검 회의와 범위 조정", "채팅 첨부와 QA 자동화는 후반부로 미루고 기여도/간트 안정화를 먼저 마감하기로 결정했습니다.", [], 47, "COMMON", "일정 조율", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 17),
        ("a42", "front", "활동 태그 한글 입력 버그 수정", "한글 조합 중 Enter 입력 시 마지막 글자가 태그로 중복되는 문제를 조합 이벤트 기준으로 수정했습니다.", ["activity_filter", "qa_regression"], 47, "BASIC", "버그 수정", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 11),
        ("a43", "back", "팀원별 활동 통계 API 추가", "팀원 페이지에서 할일뿐 아니라 활동, 도움, 검토중, 공통 활동 수를 함께 볼 수 있게 집계했습니다.", ["activity_log", "qa_regression"], 48, "BASIC", "통계", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 14),
        ("a44", "front", "팀원 페이지 활동 통계 표시", "팀원 카드에 할일 통계와 활동 통계를 나란히 표시해 실제 참여도가 드러나도록 개선했습니다.", ["activity_log"], 48, "BASIC", "UI 개선", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 15),
        ("a45", "design", "데모용 화면 문구 점검", "프로젝트 선택 카드와 마이페이지에서 권한용 역할과 표시 역할이 혼동되지 않도록 문구를 검토했습니다.", ["demo_script", "responsive_workspace"], 49, "COMMON", "데모 준비", "FINALIZATION", None, "NORMAL", "SELF_REPORTED", 16),
        ("a46", "back", "채팅 첨부파일 만료 정책 설계", "이미지와 파일을 5일간 보관하고 만료 후 삭제된 파일로 표시하는 정책과 정리 작업 기준을 정리했습니다.", ["chat_files"], 49, "BASIC", "파일 정책", "DRAFTING", None, "NORMAL", "SELF_REPORTED", 10),
        ("a47", "front", "간트 좌우 스크롤 오늘 이동 버그 수정", "마우스 휠 좌우 스크롤 시 오늘 기준선으로 튀는 문제를 스크롤 보존 방식으로 수정했습니다.", ["gantt_hierarchy", "qa_regression"], 50, "BASIC", "버그 수정", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 12),
        ("a48", "lead", "QA 체크리스트 초안 작성", "로그인, 프로젝트, 할일, 활동, 기여도, 채팅의 핵심 회귀 테스트 항목을 정리했습니다.", ["qa_regression"], 50, "BASIC", "QA", "FINALIZATION", None, "NORMAL", "SELF_REPORTED", 17),
        ("a49", "design", "발표 흐름 초안 작성", "누누잘의 문제 상황, 핵심 기능, AI 기여도 데모 순서를 발표 자료 흐름으로 정리했습니다.", ["demo_script"], 51, "BASIC", "발표 준비", "FINALIZATION", None, "NORMAL", "SELF_REPORTED", 14),
        ("a50", "front", "채팅 첨부 UI 초안", "이미지와 파일을 여러 메시지로 분리해 전송하는 UI 흐름과 미리보기 크기 기준을 작성했습니다.", ["chat_files"], 51, "PEER_SUPPORT", "UI 설계", "SUPPORT", "back", "UNDER_REVIEW", "PEER_CONFIRMED", 11),
        ("a51", "back", "기여도 이벤트 SSE 재연결 검토", "AI 측정 완료 이벤트가 세션 revoke 이후에도 전달되지 않도록 세션 검증 흐름을 점검했습니다.", ["objection_queue", "auth_session"], 52, "BASIC", "보안 개선", "REFINEMENT", None, "NORMAL", "SELF_REPORTED", 15),
        ("a52", "lead", "데모 데이터 현실감 기준 정리", "스크린샷에서 실제 중반 프로젝트처럼 보이도록 팀원 수, 할일 계층, 활동 밀도 기준을 정리했습니다.", ["demo_script"], 52, "COMMON", "데모 준비", "FINALIZATION", None, "NORMAL", "SELF_REPORTED", 16),
    ]
    for spec in activity_specs:
        make_activity(*spec)

    revision = models.ActivityRevisionHistory(
        activity_id=activities_by_key["a42"].id,
        edited_by_user_id=frontend.id,
        previous_title="태그 입력 버그 수정",
        previous_content="Enter 입력 시 마지막 글자가 한 번 더 들어가는 문제를 수정했습니다.",
        previous_contribution_phase="REFINEMENT",
        previous_credibility_level="SELF_REPORTED",
        previous_review_state="NORMAL",
        change_reason="한글 IME 조합 이벤트가 원인임을 확인해 수정 내용을 보강했습니다.",
        edited_at=at(47, 12),
    )
    session.add(revision)
    session.flush()

    analysis = models.AiAnalysis(
        project_id=project.id,
        requested_by_user_id=leader.id,
        analysis_start_date=project_start,
        analysis_end_date=day(52),
        model_name="gemini-2.5-flash",
        prompt_version="v3",
        policy_version="v2",
        analysis_mode="DISPUTE_AWARE",
        snapshot_at=at(52, 18),
        disputed_activity_count=2,
        low_credibility_activity_count=0,
        excluded_activity_count=0,
        status="COMPLETED",
        input_summary="프로젝트 중반까지의 할일 완료도, 활동 기록, 팀원 지원, 기여도 이의제기 흐름을 요약해 분석했습니다.",
        disclaimer="더미 데이터 기반 기여도 분석 결과이며 실제 평가는 모델과 프롬프트 설정에 따라 달라질 수 있습니다.",
        created_at=at(52, 18),
        completed_at=at(52, 18, 30),
    )
    session.add(analysis)
    session.flush()

    contribution_results = [
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=leader.id,
            reference_score=Decimal("25.00"),
            confidence_score=Decimal("86.00"),
            result_status="NORMAL",
            execution_score=Decimal("22.00"),
            collaboration_score=Decimal("29.00"),
            documentation_score=Decimal("27.00"),
            problem_solving_score=Decimal("24.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="프로젝트 방향 설정, 기여도 정책, 일정 조율, QA 기준 정리에 꾸준히 기여했습니다.",
            rationale="초기 문제 정의부터 중간 범위 조정, AI 입력 범위 정리, QA 체크리스트까지 팀 전체 의사결정과 품질 기준을 만든 활동이 많았습니다.",
            public_explanation="김누누 팀원은 프로젝트 리드로서 일정, 정책, 품질 기준을 안정적으로 잡았습니다.",
            uncertainty_note="직접 구현량은 백엔드/프론트 담당자보다 적지만 조율과 정책 산출물이 전체 방향성에 영향을 주었습니다.",
            warning_note="",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=frontend.id,
            reference_score=Decimal("28.00"),
            confidence_score=Decimal("88.00"),
            result_status="NORMAL",
            execution_score=Decimal("31.00"),
            collaboration_score=Decimal("26.00"),
            documentation_score=Decimal("22.00"),
            problem_solving_score=Decimal("29.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="프론트엔드 핵심 화면, 간트차트, 활동 필터, 기여도 UI, 반응형 개선에 높은 기여를 했습니다.",
            rationale="사용자에게 직접 보이는 화면 대부분을 구현했고, 활동/간트/기여도/채팅 UI의 사용성 문제를 지속적으로 개선했습니다.",
            public_explanation="한서준 팀원은 제품 사용성을 결정하는 주요 화면 구현을 담당했습니다.",
            uncertainty_note="최근 채팅 첨부 UI는 아직 검토 중이라 최종 반영 정도가 달라질 수 있습니다.",
            warning_note="",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=backend.id,
            reference_score=Decimal("30.00"),
            confidence_score=Decimal("89.00"),
            result_status="UNDER_REVIEW",
            execution_score=Decimal("32.00"),
            collaboration_score=Decimal("28.00"),
            documentation_score=Decimal("23.00"),
            problem_solving_score=Decimal("32.00"),
            disputed_activity_count=1,
            down_weighted_activity_count=0,
            summary="인증, DB, 활동/할일 API, S3, AI 연동, WebSocket 등 기반 기능에 가장 넓게 기여했습니다.",
            rationale="백엔드 핵심 기능의 범위가 넓고 프론트와의 API 계약 지원도 반복적으로 수행했습니다. 다만 채팅 읽음 카운트 일부는 검토 중입니다.",
            public_explanation="유하린 팀원은 서비스 기반 기능과 데이터 흐름 대부분을 안정적으로 구현했습니다.",
            uncertainty_note="채팅 읽음 카운트 관련 활동 하나가 검토 중이라 일부 평가는 재검토 여지가 있습니다.",
            warning_note="검토 중인 팀원 지원 활동이 있습니다.",
        ),
        models.ContributionResult(
            analysis_id=analysis.id,
            target_user_id=designer.id,
            reference_score=Decimal("17.00"),
            confidence_score=Decimal("82.00"),
            result_status="NORMAL",
            execution_score=Decimal("15.00"),
            collaboration_score=Decimal("20.00"),
            documentation_score=Decimal("19.00"),
            problem_solving_score=Decimal("15.00"),
            disputed_activity_count=0,
            down_weighted_activity_count=0,
            summary="온보딩, 정보 구조, 화면 복잡도 리뷰, 데모 흐름 정리에 기여했습니다.",
            rationale="직접 구현보다는 사용성 리뷰와 화면 구조 정리에 집중했으며, 필터와 기여도 페이지 UX 개선 방향을 제안했습니다.",
            public_explanation="오지민 팀원은 사용자가 이해하기 쉬운 화면 흐름과 데모 품질을 만드는 데 기여했습니다.",
            uncertainty_note="후반부 발표 자료와 데모 시나리오는 아직 진행 예정 작업이 남아 있습니다.",
            warning_note="",
        ),
    ]
    session.add_all(contribution_results)
    session.flush()
    contribution_result_by_user_id = {result.target_user_id: result for result in contribution_results}

    feedback_reviews = [
        models.FeedbackReview(
            project_id=project.id,
            author_user_id=frontend.id,
            target_user_id=backend.id,
            activity_id=activities_by_key["a36"].id,
            request_type="SUPPLEMENT",
            visibility="LEADER_ONLY",
            requester_hidden_from_target=False,
            content="읽음 카운트 계산 기준이 화면에서 기대한 위치와 다르게 보인 부분이 있어 처리 기준 설명을 보강해 주세요.",
            request_status="UNDER_REVIEW",
            ai_impact_mode="LOWER_CONFIDENCE_ONLY",
            created_at=at(45, 18),
            updated_at=at(45, 18, 10),
        ),
        models.FeedbackReview(
            project_id=project.id,
            author_user_id=designer.id,
            target_user_id=frontend.id,
            contribution_result_id=contribution_result_by_user_id[frontend.id].id,
            request_type="RESULT_DISPUTE",
            visibility="LEADER_ONLY",
            requester_hidden_from_target=False,
            content="기여도 UI 개선 과정에서 UX 리뷰가 프론트 구현 근거로 많이 반영되었으니 협업 기여도도 함께 봐야 합니다.",
            request_status="OPEN",
            ai_impact_mode="REQUIRE_REANALYSIS",
            created_at=at(49, 18),
            updated_at=at(49, 18),
        ),
        models.FeedbackReview(
            project_id=project.id,
            author_user_id=leader.id,
            target_user_id=backend.id,
            contribution_result_id=contribution_result_by_user_id[backend.id].id,
            request_type="RESULT_DISPUTE",
            visibility="LEADER_ONLY",
            requester_hidden_from_target=False,
            content="백엔드 범위가 넓어 높은 기여도는 타당하지만, 검토 중인 채팅 읽음 카운트 이슈를 반영해 근거를 보강해야 합니다.",
            request_status="UNDER_REVIEW",
            ai_impact_mode="REQUIRE_REANALYSIS",
            reviewed_by_user_id=leader.id,
            created_at=at(52, 18),
            updated_at=at(52, 18, 10),
            reviewed_at=at(52, 18, 10),
            resolution_note="다음 재측정 시 채팅 읽음 카운트 검토 결과를 함께 반영합니다.",
        ),
    ]
    session.add_all(feedback_reviews)
    session.flush()

    evidence_items = [
        models.Evidence(
            activity_id=activities_by_key["a20"].id,
            uploaded_by_user_id=frontend.id,
            evidence_type="IMAGE",
            evidence_role="OUTPUT",
            file_name="gantt-overview.png",
            resource_url="https://example.com/evidence/gantt-overview.png",
            description="간트차트 계층형 일정 화면 캡처본.",
            integrity_hash="sha256-gantt-overview",
            verification_status="SELF_SUBMITTED",
            captured_at=at(33, 18),
        ),
        models.Evidence(
            activity_id=activities_by_key["a27"].id,
            uploaded_by_user_id=backend.id,
            evidence_type="LINK",
            evidence_role="SUPPORTING",
            resource_url="https://example.com/evidence/contribution-snapshot-spec",
            description="AI 기여도 스냅샷 입력 구조 문서.",
            verification_status="VERIFIED",
            captured_at=at(39, 18),
        ),
        models.Evidence(
            feedback_review_id=feedback_reviews[1].id,
            uploaded_by_user_id=designer.id,
            evidence_type="LINK",
            evidence_role="SUPPORTING",
            resource_url="https://example.com/evidence/contribution-ux-review",
            description="기여도 페이지 정보 구조 리뷰 문서.",
            verification_status="SELF_SUBMITTED",
            captured_at=at(49, 17),
        ),
    ]
    session.add_all(evidence_items)
    session.commit()

    return {
        "status": "created",
        "users": len(users),
        "projects": 1,
        "project_join_requests": len(join_requests),
        "project_members": len(project_members),
        "work_items": len(work_items_by_key),
        "work_item_dependencies": len(dependency_pairs),
        "activities": len(activities_by_key),
        "activity_revisions": 1,
        "ai_analyses": 1,
        "contribution_results": len(contribution_results),
        "feedback_reviews": len(feedback_reviews),
        "evidence_items": len(evidence_items),
    }

def create_tables_and_seed_dummy_data(*, reset_existing: bool = False) -> dict[str, int | str]:
    create_tables()
    session = get_session()
    try:
        return insert_dummy_data(session, reset_existing=reset_existing)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.get("/drop-and-create", summary="Databases reset (drop and create tables)")
def databases() -> dict[str, str]:
    raise HTTPException(status_code=403, detail="DB reset API is disabled to prevent accidental data loss.")


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
        return create_tables_and_seed_dummy_data(reset_existing=False)
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
