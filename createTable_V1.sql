CREATE TABLE app_user (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    provider VARCHAR(20) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,

    email VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,

    student_id VARCHAR(50),
    department VARCHAR(100),
    profile_image_url TEXT,

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    last_login_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,

    CONSTRAINT uq_app_user_provider UNIQUE (provider, provider_user_id),
    CONSTRAINT uq_app_user_email UNIQUE (email),

    CONSTRAINT chk_app_user_provider
        CHECK (provider IN ('GOOGLE', 'KAKAO', 'NAVER')),

    CONSTRAINT chk_app_user_status
        CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DELETED'))
);

CREATE TABLE project (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',

    created_by_user_id BIGINT NOT NULL,

    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'PLANNING',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_project_created_by_user
        FOREIGN KEY (created_by_user_id)
        REFERENCES app_user(id),

    CONSTRAINT chk_project_status
        CHECK (status IN ('PLANNING', 'IN_PROGRESS', 'DONE')),

    CONSTRAINT chk_project_date_range
        CHECK (end_date >= start_date)
);	

CREATE TABLE project_member (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,

    project_role VARCHAR(20) NOT NULL DEFAULT 'MEMBER',
    position_label VARCHAR(100) NOT NULL,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP,
    memo TEXT,

    CONSTRAINT fk_project_member_project
        FOREIGN KEY (project_id)
        REFERENCES project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_project_member_user
        FOREIGN KEY (user_id)
        REFERENCES app_user(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_project_member_project_user
        UNIQUE (project_id, user_id),

    CONSTRAINT chk_project_member_role
        CHECK (project_role IN ('LEADER', 'MEMBER')),

    CONSTRAINT chk_project_member_time
        CHECK (left_at IS NULL OR left_at >= joined_at)
);

CREATE TABLE work_item (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL,
    creator_user_id BIGINT NOT NULL,
    assignee_user_id BIGINT,

    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',

    status VARCHAR(20) NOT NULL DEFAULT 'TODO',
    priority VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',

    due_date DATE,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_work_item_project
        FOREIGN KEY (project_id)
        REFERENCES project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_work_item_creator_user
        FOREIGN KEY (creator_user_id)
        REFERENCES app_user(id),

    CONSTRAINT fk_work_item_assignee_user
        FOREIGN KEY (assignee_user_id)
        REFERENCES app_user(id),

    CONSTRAINT chk_work_item_status
        CHECK (status IN ('TODO', 'IN_PROGRESS', 'DONE')),

    CONSTRAINT chk_work_item_priority
        CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH')),

    CONSTRAINT chk_work_item_time_order
        CHECK (
            (started_at IS NULL OR started_at >= created_at)
            AND
            (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
        ) 
);

CREATE TABLE activity (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL,
    work_item_id BIGINT,
    actor_user_id BIGINT NOT NULL,

    activity_type VARCHAR(40) NOT NULL,
    contribution_phase VARCHAR(20) NOT NULL,

    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,

    source_type VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    credibility_level VARCHAR(30) NOT NULL DEFAULT 'SELF_REPORTED',
    review_state VARCHAR(20) NOT NULL DEFAULT 'NORMAL',

    version INTEGER NOT NULL DEFAULT 1,

    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    last_edited_by_user_id BIGINT,
    correction_reason TEXT,

    CONSTRAINT fk_activity_project
        FOREIGN KEY (project_id)
        REFERENCES project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_activity_work_item
        FOREIGN KEY (work_item_id)
        REFERENCES work_item(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_activity_actor_user
        FOREIGN KEY (actor_user_id)
        REFERENCES app_user(id),

    CONSTRAINT fk_activity_last_edited_user
        FOREIGN KEY (last_edited_by_user_id)
        REFERENCES app_user(id),

    CONSTRAINT chk_activity_type
        CHECK (
            activity_type IN (
                'MATERIAL_COLLECTION',
                'MEETING_RECORD',
                'CONTENT_EDITING',
                'FINALIZATION'
            )
        ),

    CONSTRAINT chk_activity_phase
        CHECK (
            contribution_phase IN (
                'PREPARATION',
                'DRAFTING',
                'REFINEMENT',
                'FINALIZATION',
                'SUPPORT'
            )
        ),

    CONSTRAINT chk_activity_source_type
        CHECK (
            source_type IN (
                'MANUAL',
                'SYSTEM_IMPORTED'
            )
        ),

    CONSTRAINT chk_activity_credibility
        CHECK (
            credibility_level IN (
                'SELF_REPORTED',
                'EVIDENCE_BACKED',
                'PEER_CONFIRMED',
                'SYSTEM_IMPORTED'
            )
        ),

    CONSTRAINT chk_activity_review_state
        CHECK (
            review_state IN (
                'NORMAL',
                'UNDER_REVIEW',
                'DISPUTED',
                'RESOLVED'
            )
        ),

    CONSTRAINT chk_activity_version
        CHECK (version >= 1),

    CONSTRAINT chk_activity_time_order
        CHECK (
            occurred_at <= updated_at
            AND created_at <= updated_at
        )
);

CREATE TABLE activity_revision_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    activity_id BIGINT NOT NULL,
    edited_by_user_id BIGINT NOT NULL,

    previous_title VARCHAR(200) NOT NULL,
    previous_content TEXT NOT NULL,
    previous_contribution_phase VARCHAR(20) NOT NULL,
    previous_credibility_level VARCHAR(30) NOT NULL,
    previous_review_state VARCHAR(20) NOT NULL,

    change_reason TEXT NOT NULL,
    edited_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_activity_revision_history_activity
        FOREIGN KEY (activity_id)
        REFERENCES activity(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_activity_revision_history_edited_by_user
        FOREIGN KEY (edited_by_user_id)
        REFERENCES app_user(id),

    CONSTRAINT chk_activity_revision_history_phase
        CHECK (
            previous_contribution_phase IN (
                'PREPARATION',
                'DRAFTING',
                'REFINEMENT',
                'FINALIZATION',
                'SUPPORT'
            )
        ),

    CONSTRAINT chk_activity_revision_history_credibility
        CHECK (
            previous_credibility_level IN (
                'SELF_REPORTED',
                'EVIDENCE_BACKED',
                'PEER_CONFIRMED',
                'SYSTEM_IMPORTED'
            )
        ),

    CONSTRAINT chk_activity_revision_history_review_state
        CHECK (
            previous_review_state IN (
                'NORMAL',
                'UNDER_REVIEW',
                'DISPUTED',
                'RESOLVED'
            )
        )
);

CREATE TABLE ai_analysis (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL,
    requested_by_user_id BIGINT NOT NULL,

    analysis_start_date DATE NOT NULL,
    analysis_end_date DATE NOT NULL,

    model_name VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(50) NOT NULL,
    policy_version VARCHAR(50) NOT NULL,

    analysis_mode VARCHAR(20) NOT NULL DEFAULT 'REGULAR',
    snapshot_at TIMESTAMP NOT NULL,

    disputed_activity_count INTEGER NOT NULL DEFAULT 0,
    low_credibility_activity_count INTEGER NOT NULL DEFAULT 0,
    excluded_activity_count INTEGER NOT NULL DEFAULT 0,

    status VARCHAR(20) NOT NULL DEFAULT 'REQUESTED',

    input_summary TEXT NOT NULL,
    disclaimer TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    CONSTRAINT fk_ai_analysis_project
        FOREIGN KEY (project_id)
        REFERENCES project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_ai_analysis_requested_by_user
        FOREIGN KEY (requested_by_user_id)
        REFERENCES app_user(id),

    CONSTRAINT chk_ai_analysis_mode
        CHECK (analysis_mode IN ('REGULAR', 'DISPUTE_AWARE')),

    CONSTRAINT chk_ai_analysis_status
        CHECK (status IN ('REQUESTED', 'PROCESSING', 'COMPLETED', 'FAILED')),

    CONSTRAINT chk_ai_analysis_date_range
        CHECK (analysis_end_date >= analysis_start_date),

    CONSTRAINT chk_ai_analysis_counts
        CHECK (
            disputed_activity_count >= 0
            AND low_credibility_activity_count >= 0
            AND excluded_activity_count >= 0
        ),

    CONSTRAINT chk_ai_analysis_completed_time
        CHECK (completed_at IS NULL OR completed_at >= created_at)
);

CREATE TABLE contribution_result (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    analysis_id BIGINT NOT NULL,
    target_user_id BIGINT NOT NULL,

    reference_score NUMERIC(5,2) NOT NULL,
    confidence_score NUMERIC(5,2) NOT NULL,

    result_status VARCHAR(20) NOT NULL DEFAULT 'NORMAL',

    execution_score NUMERIC(5,2) NOT NULL DEFAULT 0,
    collaboration_score NUMERIC(5,2) NOT NULL DEFAULT 0,
    documentation_score NUMERIC(5,2) NOT NULL DEFAULT 0,
    problem_solving_score NUMERIC(5,2) NOT NULL DEFAULT 0,

    disputed_activity_count INTEGER NOT NULL DEFAULT 0,
    down_weighted_activity_count INTEGER NOT NULL DEFAULT 0,

    summary TEXT NOT NULL,
    rationale TEXT NOT NULL,
    public_explanation TEXT NOT NULL,
    uncertainty_note TEXT NOT NULL,
    warning_note TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_contribution_result_analysis
        FOREIGN KEY (analysis_id)
        REFERENCES ai_analysis(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_contribution_result_target_user
        FOREIGN KEY (target_user_id)
        REFERENCES app_user(id),

    CONSTRAINT uq_contribution_result_analysis_user
        UNIQUE (analysis_id, target_user_id),

    CONSTRAINT chk_contribution_result_status
        CHECK (
            result_status IN (
                'NORMAL',
                'LOW_CONFIDENCE',
                'UNDER_REVIEW',
                'DISPUTED'
            )
        ),

    CONSTRAINT chk_contribution_result_scores
        CHECK (
            reference_score >= 0
            AND confidence_score >= 0
            AND execution_score >= 0
            AND collaboration_score >= 0
            AND documentation_score >= 0
            AND problem_solving_score >= 0
        ),

    CONSTRAINT chk_contribution_result_counts
        CHECK (
            disputed_activity_count >= 0
            AND down_weighted_activity_count >= 0
        )
);

CREATE TABLE feedback_review (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    project_id BIGINT NOT NULL,
    author_user_id BIGINT NOT NULL,
    target_user_id BIGINT,

    activity_id BIGINT,
    analysis_id BIGINT,
    contribution_result_id BIGINT,

    request_type VARCHAR(30) NOT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'LEADER_ONLY',
    requester_hidden_from_target BOOLEAN NOT NULL DEFAULT TRUE,

    content TEXT NOT NULL,

    request_status VARCHAR(30) NOT NULL DEFAULT 'OPEN',
    ai_impact_mode VARCHAR(30) NOT NULL DEFAULT 'NONE',

    reviewed_by_user_id BIGINT,
    reviewed_at TIMESTAMP,
    resolution_note TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_feedback_review_project
        FOREIGN KEY (project_id)
        REFERENCES project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_feedback_review_author_user
        FOREIGN KEY (author_user_id)
        REFERENCES app_user(id),

    CONSTRAINT fk_feedback_review_target_user
        FOREIGN KEY (target_user_id)
        REFERENCES app_user(id),

    CONSTRAINT fk_feedback_review_activity
        FOREIGN KEY (activity_id)
        REFERENCES activity(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_feedback_review_analysis
        FOREIGN KEY (analysis_id)
        REFERENCES ai_analysis(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_feedback_review_reviewed_by_user
        FOREIGN KEY (reviewed_by_user_id)
        REFERENCES app_user(id),
        
    CONSTRAINT fk_feedback_review_contribution_result
		  FOREIGN KEY (contribution_result_id)
		  REFERENCES contribution_result(id)
	     ON DELETE CASCADE,

    CONSTRAINT chk_feedback_review_target_exactly_one
        CHECK (
            ((activity_id IS NOT NULL)::int +
             (analysis_id IS NOT NULL)::int +
             (contribution_result_id IS NOT NULL)::int) = 1
        ),

    CONSTRAINT chk_feedback_review_request_type
        CHECK (
            request_type IN (
                'SUPPLEMENT',
                'CO_CONTRIBUTOR_REQUEST',
                'OVERCLAIM_CONCERN',
                'RESULT_DISPUTE',
                'CORRECTION_REQUEST'
            )
        ),

    CONSTRAINT chk_feedback_review_visibility
        CHECK (
            visibility IN (
                'SYSTEM_ONLY',
                'LEADER_ONLY'
            )
        ),

    CONSTRAINT chk_feedback_review_status
        CHECK (
            request_status IN (
                'OPEN',
                'UNDER_REVIEW',
                'REFLECTED',
                'REJECTED',
                'PARTIALLY_REFLECTED'
            )
        ),

    CONSTRAINT chk_feedback_review_ai_impact_mode
        CHECK (
            ai_impact_mode IN (
                'NONE',
                'LOWER_CONFIDENCE_ONLY',
                'REQUIRE_REANALYSIS',
                'DOWNWEIGHT_AFTER_REVIEW'
            )
        ),

    CONSTRAINT chk_feedback_review_review_time
        CHECK (reviewed_at IS NULL OR reviewed_at >= created_at)
);


CREATE TABLE evidence (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    activity_id BIGINT,
    feedback_review_id BIGINT,
    uploaded_by_user_id BIGINT NOT NULL,

    evidence_type VARCHAR(20) NOT NULL,
    evidence_role VARCHAR(20) NOT NULL,

    file_name VARCHAR(255),
    resource_url TEXT NOT NULL,
    description TEXT,
    integrity_hash VARCHAR(255),

    verification_status VARCHAR(20) NOT NULL DEFAULT 'SELF_SUBMITTED',
    captured_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_evidence_activity
        FOREIGN KEY (activity_id)
        REFERENCES activity(id)
        ON DELETE CASCADE,
   
	 CONSTRAINT fk_evidence_feedback_review
		  FOREIGN KEY (feedback_review_id)
		  REFERENCES feedback_review(id)
		  ON DELETE CASCADE,

    CONSTRAINT fk_evidence_uploaded_by_user
        FOREIGN KEY (uploaded_by_user_id)
        REFERENCES app_user(id),

    CONSTRAINT chk_evidence_target_exactly_one
        CHECK (
            (activity_id IS NOT NULL AND feedback_review_id IS NULL)
            OR
            (activity_id IS NULL AND feedback_review_id IS NOT NULL)
        ),

    CONSTRAINT chk_evidence_type
        CHECK (
            evidence_type IN (
                'FILE',
                'LINK',
                'IMAGE'
            )
        ),

    CONSTRAINT chk_evidence_role
        CHECK (
            evidence_role IN (
                'SUPPORTING',
                'CONTRADICTING',
                'OUTPUT'
            )
        ),

    CONSTRAINT chk_evidence_verification_status
        CHECK (
            verification_status IN (
                'SELF_SUBMITTED',
                'SYSTEM_LINKED',
                'VERIFIED',
                'DISPUTED'
            )
        )
);