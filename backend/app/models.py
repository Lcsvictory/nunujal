from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    DATE,
    INTEGER,
    NUMERIC,
    TEXT,
    TIMESTAMP,
    VARCHAR,
    CheckConstraint,
    ForeignKey,
    Identity,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_app_user_provider"),
        UniqueConstraint("email", name="uq_app_user_email"),
        CheckConstraint("provider IN ('GOOGLE', 'KAKAO', 'NAVER')", name="chk_app_user_provider"),
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'DELETED')", name="chk_app_user_status"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    provider: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    email: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    student_id: Mapped[str] = mapped_column(VARCHAR(50), nullable=True)
    department: Mapped[str] = mapped_column(VARCHAR(100), nullable=True)
    profile_image_url: Mapped[str] = mapped_column(TEXT, nullable=True)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'"))
    last_login_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    deleted_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)

    created_projects: Mapped[list["Project"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="Project.created_by_user_id",
    )
    project_memberships: Mapped[list["ProjectMember"]] = relationship(back_populates="user")
    sent_join_requests: Mapped[list["ProjectJoinRequest"]] = relationship(
        back_populates="requester_user",
        foreign_keys="ProjectJoinRequest.requester_user_id",
    )
    reviewed_join_requests: Mapped[list["ProjectJoinRequest"]] = relationship(
        back_populates="reviewed_by_user",
        foreign_keys="ProjectJoinRequest.reviewed_by_user_id",
    )
    created_work_items: Mapped[list["WorkItem"]] = relationship(
        back_populates="creator_user",
        foreign_keys="WorkItem.creator_user_id",
    )
    assigned_work_items: Mapped[list["WorkItem"]] = relationship(
        back_populates="assignee_user",
        foreign_keys="WorkItem.assignee_user_id",
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="actor_user",
        foreign_keys="Activity.actor_user_id",
    )
    edited_activities: Mapped[list["Activity"]] = relationship(
        back_populates="last_edited_by_user",
        foreign_keys="Activity.last_edited_by_user_id",
    )
    activity_revision_histories: Mapped[list["ActivityRevisionHistory"]] = relationship(
        back_populates="edited_by_user"
    )
    requested_analyses: Mapped[list["AiAnalysis"]] = relationship(back_populates="requested_by_user")
    contribution_results: Mapped[list["ContributionResult"]] = relationship(back_populates="target_user")
    authored_feedback_reviews: Mapped[list["FeedbackReview"]] = relationship(
        back_populates="author_user",
        foreign_keys="FeedbackReview.author_user_id",
    )
    targeted_feedback_reviews: Mapped[list["FeedbackReview"]] = relationship(
        back_populates="target_user",
        foreign_keys="FeedbackReview.target_user_id",
    )
    reviewed_feedback_reviews: Mapped[list["FeedbackReview"]] = relationship(
        back_populates="reviewed_by_user",
        foreign_keys="FeedbackReview.reviewed_by_user_id",
    )
    uploaded_evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="uploaded_by_user")



class Project(Base):
    __tablename__ = "project"
    __table_args__ = (
        UniqueConstraint("join_code", name="uq_project_join_code"),
        CheckConstraint("status IN ('PLANNING', 'IN_PROGRESS', 'DONE')", name="chk_project_status"),
        CheckConstraint(
            "join_policy IN ('AUTO_APPROVE', 'LEADER_APPROVE')",
            name="chk_project_join_policy",
        ),
        CheckConstraint("end_date >= start_date", name="chk_project_date_range"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    description: Mapped[str] = mapped_column(TEXT, nullable=False, default="", server_default=text("''"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    join_code: Mapped[str] = mapped_column(VARCHAR(12), nullable=False)
    join_code_active: Mapped[bool] = mapped_column(
        BOOLEAN,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
    )
    join_policy: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="LEADER_APPROVE",
        server_default=text("'LEADER_APPROVE'"),
    )
    join_code_created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    join_code_expires_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    start_date: Mapped[date] = mapped_column(DATE, nullable=False)
    end_date: Mapped[date] = mapped_column(DATE, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="PLANNING", server_default=text("'PLANNING'"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    created_by_user: Mapped[AppUser] = relationship(back_populates="created_projects")
    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    join_requests: Mapped[list["ProjectJoinRequest"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    work_items: Mapped[list["WorkItem"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    ai_analyses: Mapped[list["AiAnalysis"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    feedback_reviews: Mapped[list["FeedbackReview"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectMember(Base):
    __tablename__ = "project_member"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
        CheckConstraint("project_role IN ('LEADER', 'MEMBER')", name="chk_project_member_role"),
        CheckConstraint("left_at IS NULL OR left_at >= joined_at", name="chk_project_member_time"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False)
    project_role: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="MEMBER", server_default=text("'MEMBER'"))
    position_label: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    left_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    memo: Mapped[str] = mapped_column(TEXT, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped[AppUser] = relationship(back_populates="project_memberships")


class ProjectJoinRequest(Base):
    __tablename__ = "project_join_request"
    __table_args__ = (
        UniqueConstraint("project_id", "requester_user_id", name="uq_project_join_request_project_user"),
        CheckConstraint(
            "request_status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELED', 'EXPIRED')",
            name="chk_project_join_request_status",
        ),
        CheckConstraint(
            "reviewed_project_role IS NULL OR reviewed_project_role IN ('LEADER', 'MEMBER')",
            name="chk_project_join_request_project_role",
        ),
        CheckConstraint(
            "reviewed_at IS NULL OR reviewed_at >= created_at",
            name="chk_project_join_request_review_time",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False)
    request_message: Mapped[str] = mapped_column(TEXT, nullable=True)
    requested_position_label: Mapped[str] = mapped_column(VARCHAR(100), nullable=True)
    request_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="PENDING",
        server_default=text("'PENDING'"),
    )
    reviewed_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    reviewed_project_role: Mapped[str] = mapped_column(VARCHAR(20), nullable=True)
    reviewed_position_label: Mapped[str] = mapped_column(VARCHAR(100), nullable=True)
    review_note: Mapped[str] = mapped_column(TEXT, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped["Project"] = relationship(back_populates="join_requests")
    requester_user: Mapped[AppUser] = relationship(
        back_populates="sent_join_requests",
        foreign_keys=[requester_user_id],
    )
    reviewed_by_user: Mapped["AppUser"] = relationship(
        back_populates="reviewed_join_requests",
        foreign_keys=[reviewed_by_user_id],
    )


class WorkItem(Base):
    __tablename__ = "work_item"
    __table_args__ = (
        CheckConstraint("status IN ('TODO', 'IN_PROGRESS', 'DONE')", name="chk_work_item_status"),
        CheckConstraint("priority IN ('LOW', 'MEDIUM', 'HIGH')", name="chk_work_item_priority"),
        CheckConstraint(
            "(started_at IS NULL OR started_at >= created_at) "
            "AND (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)",
            name="chk_work_item_time_order",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    assignee_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    description: Mapped[str] = mapped_column(TEXT, nullable=False, default="", server_default=text("''"))
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="TODO", server_default=text("'TODO'"))
    priority: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="MEDIUM", server_default=text("'MEDIUM'"))
    due_date: Mapped[date] = mapped_column(DATE, nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped["Project"] = relationship(back_populates="work_items")
    creator_user: Mapped[AppUser] = relationship(
        back_populates="created_work_items",
        foreign_keys=[creator_user_id],
    )
    assignee_user: Mapped["AppUser"] = relationship(
        back_populates="assigned_work_items",
        foreign_keys=[assignee_user_id],
    )
    activities: Mapped[list["Activity"]] = relationship(back_populates="work_item")


class Activity(Base):
    __tablename__ = "activity"
    __table_args__ = (
        CheckConstraint(
            "activity_type IN ("
            "'MATERIAL_COLLECTION', 'MEETING_RECORD', 'CONTENT_EDITING', 'FINALIZATION'"
            ")",
            name="chk_activity_type",
        ),
        CheckConstraint(
            "contribution_phase IN ("
            "'PREPARATION', 'DRAFTING', 'REFINEMENT', 'FINALIZATION', 'SUPPORT'"
            ")",
            name="chk_activity_phase",
        ),
        CheckConstraint("source_type IN ('MANUAL', 'SYSTEM_IMPORTED')", name="chk_activity_source_type"),
        CheckConstraint(
            "credibility_level IN ("
            "'SELF_REPORTED', 'EVIDENCE_BACKED', 'PEER_CONFIRMED', 'SYSTEM_IMPORTED'"
            ")",
            name="chk_activity_credibility",
        ),
        CheckConstraint(
            "review_state IN ('NORMAL', 'UNDER_REVIEW', 'DISPUTED', 'RESOLVED')",
            name="chk_activity_review_state",
        ),
        CheckConstraint("version >= 1", name="chk_activity_version"),
        CheckConstraint("occurred_at <= updated_at AND created_at <= updated_at", name="chk_activity_time_order"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    work_item_id: Mapped[int] = mapped_column(ForeignKey("work_item.id", ondelete="SET NULL"), nullable=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    activity_type: Mapped[str] = mapped_column(VARCHAR(40), nullable=False)
    contribution_phase: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    source_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="MANUAL", server_default=text("'MANUAL'"))
    credibility_level: Mapped[str] = mapped_column(
        VARCHAR(30),
        nullable=False,
        default="SELF_REPORTED",
        server_default=text("'SELF_REPORTED'"),
    )
    review_state: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="NORMAL", server_default=text("'NORMAL'"))
    version: Mapped[int] = mapped_column(INTEGER, nullable=False, default=1, server_default=text("1"))
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    last_edited_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    correction_reason: Mapped[str] = mapped_column(TEXT, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="activities")
    work_item: Mapped["WorkItem"] = relationship(back_populates="activities")
    actor_user: Mapped[AppUser] = relationship(back_populates="activities", foreign_keys=[actor_user_id])
    last_edited_by_user: Mapped["AppUser"] = relationship(
        back_populates="edited_activities",
        foreign_keys=[last_edited_by_user_id],
    )
    revision_histories: Mapped[list["ActivityRevisionHistory"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    feedback_reviews: Mapped[list["FeedbackReview"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    evidence_items: Mapped[list["Evidence"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )


class ActivityRevisionHistory(Base):
    __tablename__ = "activity_revision_history"
    __table_args__ = (
        CheckConstraint(
            "previous_contribution_phase IN ("
            "'PREPARATION', 'DRAFTING', 'REFINEMENT', 'FINALIZATION', 'SUPPORT'"
            ")",
            name="chk_activity_revision_history_phase",
        ),
        CheckConstraint(
            "previous_credibility_level IN ("
            "'SELF_REPORTED', 'EVIDENCE_BACKED', 'PEER_CONFIRMED', 'SYSTEM_IMPORTED'"
            ")",
            name="chk_activity_revision_history_credibility",
        ),
        CheckConstraint(
            "previous_review_state IN ('NORMAL', 'UNDER_REVIEW', 'DISPUTED', 'RESOLVED')",
            name="chk_activity_revision_history_review_state",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id", ondelete="CASCADE"), nullable=False)
    edited_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    previous_title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    previous_content: Mapped[str] = mapped_column(TEXT, nullable=False)
    previous_contribution_phase: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    previous_credibility_level: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)
    previous_review_state: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    change_reason: Mapped[str] = mapped_column(TEXT, nullable=False)
    edited_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    activity: Mapped["Activity"] = relationship(back_populates="revision_histories")
    edited_by_user: Mapped[AppUser] = relationship(back_populates="activity_revision_histories")


class AiAnalysis(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = (
        CheckConstraint("analysis_mode IN ('REGULAR', 'DISPUTE_AWARE')", name="chk_ai_analysis_mode"),
        CheckConstraint(
            "status IN ('REQUESTED', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="chk_ai_analysis_status",
        ),
        CheckConstraint("analysis_end_date >= analysis_start_date", name="chk_ai_analysis_date_range"),
        CheckConstraint(
            "disputed_activity_count >= 0 "
            "AND low_credibility_activity_count >= 0 "
            "AND excluded_activity_count >= 0",
            name="chk_ai_analysis_counts",
        ),
        CheckConstraint("completed_at IS NULL OR completed_at >= created_at", name="chk_ai_analysis_completed_time"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    analysis_start_date: Mapped[date] = mapped_column(DATE, nullable=False)
    analysis_end_date: Mapped[date] = mapped_column(DATE, nullable=False)
    model_name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    policy_version: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    analysis_mode: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="REGULAR", server_default=text("'REGULAR'"))
    snapshot_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    disputed_activity_count: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0, server_default=text("0"))
    low_credibility_activity_count: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0, server_default=text("0"))
    excluded_activity_count: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0, server_default=text("0"))
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="REQUESTED", server_default=text("'REQUESTED'"))
    input_summary: Mapped[str] = mapped_column(TEXT, nullable=False)
    disclaimer: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="ai_analyses")
    requested_by_user: Mapped[AppUser] = relationship(back_populates="requested_analyses")
    contribution_results: Mapped[list["ContributionResult"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    feedback_reviews: Mapped[list["FeedbackReview"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class ContributionResult(Base):
    __tablename__ = "contribution_result"
    __table_args__ = (
        UniqueConstraint("analysis_id", "target_user_id", name="uq_contribution_result_analysis_user"),
        CheckConstraint(
            "result_status IN ('NORMAL', 'LOW_CONFIDENCE', 'UNDER_REVIEW', 'DISPUTED')",
            name="chk_contribution_result_status",
        ),
        CheckConstraint(
            "reference_score >= 0 "
            "AND confidence_score >= 0 "
            "AND execution_score >= 0 "
            "AND collaboration_score >= 0 "
            "AND documentation_score >= 0 "
            "AND problem_solving_score >= 0",
            name="chk_contribution_result_scores",
        ),
        CheckConstraint(
            "disputed_activity_count >= 0 AND down_weighted_activity_count >= 0",
            name="chk_contribution_result_counts",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analysis.id", ondelete="CASCADE"), nullable=False)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    reference_score: Mapped[Decimal] = mapped_column(NUMERIC(5, 2), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(NUMERIC(5, 2), nullable=False)
    result_status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="NORMAL", server_default=text("'NORMAL'"))
    execution_score: Mapped[Decimal] = mapped_column(NUMERIC(5, 2), nullable=False, default=0, server_default=text("0"))
    collaboration_score: Mapped[Decimal] = mapped_column(NUMERIC(5, 2), nullable=False, default=0, server_default=text("0"))
    documentation_score: Mapped[Decimal] = mapped_column(NUMERIC(5, 2), nullable=False, default=0, server_default=text("0"))
    problem_solving_score: Mapped[Decimal] = mapped_column(NUMERIC(5, 2), nullable=False, default=0, server_default=text("0"))
    disputed_activity_count: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0, server_default=text("0"))
    down_weighted_activity_count: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0, server_default=text("0"))
    summary: Mapped[str] = mapped_column(TEXT, nullable=False)
    rationale: Mapped[str] = mapped_column(TEXT, nullable=False)
    public_explanation: Mapped[str] = mapped_column(TEXT, nullable=False)
    uncertainty_note: Mapped[str] = mapped_column(TEXT, nullable=False)
    warning_note: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    analysis: Mapped["AiAnalysis"] = relationship(back_populates="contribution_results")
    target_user: Mapped[AppUser] = relationship(back_populates="contribution_results")
    feedback_reviews: Mapped[list["FeedbackReview"]] = relationship(
        back_populates="contribution_result",
        cascade="all, delete-orphan",
    )


class FeedbackReview(Base):
    __tablename__ = "feedback_review"
    __table_args__ = (
        CheckConstraint(
            "((activity_id IS NOT NULL)::int + "
            "(analysis_id IS NOT NULL)::int + "
            "(contribution_result_id IS NOT NULL)::int) = 1",
            name="chk_feedback_review_target_exactly_one",
        ),
        CheckConstraint(
            "request_type IN ("
            "'SUPPLEMENT', 'CO_CONTRIBUTOR_REQUEST', 'OVERCLAIM_CONCERN', "
            "'RESULT_DISPUTE', 'CORRECTION_REQUEST'"
            ")",
            name="chk_feedback_review_request_type",
        ),
        CheckConstraint("visibility IN ('SYSTEM_ONLY', 'LEADER_ONLY')", name="chk_feedback_review_visibility"),
        CheckConstraint(
            "request_status IN ("
            "'OPEN', 'UNDER_REVIEW', 'REFLECTED', 'REJECTED', 'PARTIALLY_REFLECTED'"
            ")",
            name="chk_feedback_review_status",
        ),
        CheckConstraint(
            "ai_impact_mode IN ("
            "'NONE', 'LOWER_CONFIDENCE_ONLY', 'REQUIRE_REANALYSIS', 'DOWNWEIGHT_AFTER_REVIEW'"
            ")",
            name="chk_feedback_review_ai_impact_mode",
        ),
        CheckConstraint("reviewed_at IS NULL OR reviewed_at >= created_at", name="chk_feedback_review_review_time"),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id", ondelete="CASCADE"), nullable=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analysis.id", ondelete="CASCADE"), nullable=True)
    contribution_result_id: Mapped[int] = mapped_column(
        ForeignKey("contribution_result.id", ondelete="CASCADE"),
        nullable=True,
    )
    request_type: Mapped[str] = mapped_column(VARCHAR(30), nullable=False)
    visibility: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="LEADER_ONLY",
        server_default=text("'LEADER_ONLY'"),
    )
    requester_hidden_from_target: Mapped[bool] = mapped_column(
        BOOLEAN,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
    )
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    request_status: Mapped[str] = mapped_column(VARCHAR(30), nullable=False, default="OPEN", server_default=text("'OPEN'"))
    ai_impact_mode: Mapped[str] = mapped_column(VARCHAR(30), nullable=False, default="NONE", server_default=text("'NONE'"))
    reviewed_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    resolution_note: Mapped[str] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped["Project"] = relationship(back_populates="feedback_reviews")
    author_user: Mapped[AppUser] = relationship(
        back_populates="authored_feedback_reviews",
        foreign_keys=[author_user_id],
    )
    target_user: Mapped["AppUser"] = relationship(
        back_populates="targeted_feedback_reviews",
        foreign_keys=[target_user_id],
    )
    activity: Mapped["Activity"] = relationship(back_populates="feedback_reviews")
    analysis: Mapped["AiAnalysis"] = relationship(back_populates="feedback_reviews")
    contribution_result: Mapped["ContributionResult"] = relationship(back_populates="feedback_reviews")
    reviewed_by_user: Mapped["AppUser"] = relationship(
        back_populates="reviewed_feedback_reviews",
        foreign_keys=[reviewed_by_user_id],
    )
    evidence_items: Mapped[list["Evidence"]] = relationship(
        back_populates="feedback_review",
        cascade="all, delete-orphan",
    )


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "(activity_id IS NOT NULL AND feedback_review_id IS NULL) "
            "OR (activity_id IS NULL AND feedback_review_id IS NOT NULL)",
            name="chk_evidence_target_exactly_one",
        ),
        CheckConstraint("evidence_type IN ('FILE', 'LINK', 'IMAGE')", name="chk_evidence_type"),
        CheckConstraint("evidence_role IN ('SUPPORTING', 'CONTRADICTING', 'OUTPUT')", name="chk_evidence_role"),
        CheckConstraint(
            "verification_status IN ('SELF_SUBMITTED', 'SYSTEM_LINKED', 'VERIFIED', 'DISPUTED')",
            name="chk_evidence_verification_status",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT, Identity(always=True), primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activity.id", ondelete="CASCADE"), nullable=True)
    feedback_review_id: Mapped[int] = mapped_column(ForeignKey("feedback_review.id", ondelete="CASCADE"), nullable=True)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    evidence_role: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    file_name: Mapped[str] = mapped_column(VARCHAR(255), nullable=True)
    resource_url: Mapped[str] = mapped_column(TEXT, nullable=False)
    description: Mapped[str] = mapped_column(TEXT, nullable=True)
    integrity_hash: Mapped[str] = mapped_column(VARCHAR(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="SELF_SUBMITTED",
        server_default=text("'SELF_SUBMITTED'"),
    )
    captured_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    activity: Mapped["Activity"] = relationship(back_populates="evidence_items")
    feedback_review: Mapped["FeedbackReview"] = relationship(back_populates="evidence_items")
    uploaded_by_user: Mapped[AppUser] = relationship(back_populates="uploaded_evidence_items")
