import type { AuthUser } from "../auth/types";

export type ProjectMembership = {
  project_member_id: number;
  project_role: string;
  position_label: string;
  joined_at: string;
  left_at: string | null;
};

export type ProjectSummary = {
  id: number;
  title: string;
  description: string;
  status: string;
  start_date: string;
  end_date: string;
  join_policy: string;
  join_code_active: boolean;
  join_code_expires_at: string | null;
  member_count: number;
  my_membership: ProjectMembership;
};

export type ProjectListResponse = {
  authenticated: boolean;
  user?: AuthUser | null;
  current_user?: AuthUser | null;
  projects: ProjectSummary[];
  count: number;
};

export type ProjectMemberActivityStats = {
  total_count: number;
  basic_count: number;
  peer_support_count: number;
  common_count: number;
  under_review_count: number;
  resolved_count: number;
};

export type ProjectMemberSummary = {
  project_member_id: number;
  user_id: number;
  name: string;
  email: string;
  profile_image_url?: string;
  project_role: string;
  position_label: string;
  activity_stats?: ProjectMemberActivityStats;
};

export type ProjectRecentActivity = {
  id: number;
  title: string;
  content: string;
  activity_category: string;
  activity_type: string;
  contribution_phase?: string;
  review_state: string;
  credibility_level?: string;
  source_type?: string;
  version?: number;
  occurred_at: string;
  created_at?: string;
  updated_at: string;
  is_modified?: boolean;
  actor: {
    id: number;
    name: string;
    profile_image_url?: string | null;
  };
  target_user: {
    id: number;
    name: string;
    profile_image_url?: string | null;
  } | null;
  work_items: {
    id: number;
    title: string;
    description?: string;
    status?: string;
    assignee?: {
      id?: number;
      name: string;
      profile_image_url?: string | null;
    } | null;
    timeline_start_date?: string;
    timeline_end_date?: string;
  }[];
  evidences?: ProjectEvidence[];
  reactions?: {
    reactor_user_id: number;
    reaction_type: string;
    created_at?: string;
  }[];
};

export type ProjectUploadedFile = {
  id: number;
  file_name: string;
  content_type: string;
  file_size_bytes: number;
  is_image: boolean;
  download_url?: string | null;
  preview_url?: string | null;
  created_at?: string;
};

export type ProjectEvidence = {
  id: number;
  evidence_type: string;
  evidence_role: string;
  file_name?: string | null;
  description?: string | null;
  resource_url?: string | null;
  uploaded_file_id?: number | null;
  uploaded_file?: ProjectUploadedFile | null;
  verification_status?: string;
  created_at?: string;
};

export type ProjectOverview = {
  total_work_items: number;
  todo_work_items: number;
  in_progress_work_items: number;
  done_work_items: number;
  completion_rate: number;
  recent_activities: ProjectRecentActivity[];
};

export type ProjectDetail = {
  id: number;
  title: string;
  description: string;
  status: string;
  start_date: string;
  end_date: string;
  join_policy: string;
  join_code: string;
  join_code_active: boolean;
  join_code_expires_at: string | null;
  member_count: number;
  my_membership: ProjectMembership;
  members: ProjectMemberSummary[];
  overview: ProjectOverview;
};

export type ProjectDetailResponse = {
  authenticated: boolean;
  current_user: AuthUser;
  project: ProjectDetail;
};

export type ProjectWorkItemSummary = {
  id: number;
  title: string;
  description: string;
  status: "TODO" | "IN_PROGRESS" | "DONE";
  priority: "LOW" | "MEDIUM" | "HIGH";
  due_date: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  timeline_start_date: string;
  timeline_end_date: string;
  duration_days: number;
  parent_work_item_id: number | null;
  gantt_sort_order: number;
  creator: {
    id: number;
    name: string;
    profile_image_url?: string;
  };
  assignee: {
    id: number;
    name: string;
    profile_image_url?: string;
  } | null;
  contributors?: {
    id: number;
    name: string;
    profile_image_url?: string;
  }[];
  attachments?: ProjectUploadedFile[];
};

export type ProjectWorkItemDependency = {
  id: number;
  predecessor_work_item_id: number;
  successor_work_item_id: number;
  created_at: string;
};

export type ProjectWorkItemListResponse = {
  project_id: number;
  count: number;
  items: ProjectWorkItemSummary[];
  dependency_count: number;
  dependencies: ProjectWorkItemDependency[];
};

export type ProjectActivityListFilters = {
  actor_user_id?: number | null;
  target_user_id?: number | null;
  author_scope?: "ALL" | "ME";
  category?: string;
  review_state?: string;
  contribution_phase?: string;
  credibility_level?: string;
  source_type?: string;
  work_item_id?: number | null;
  work_item_ids?: string;
  work_item_assignee_user_id?: number | null;
  q?: string;
  tag?: string;
  date_from?: string;
  date_to?: string;
  has_evidence?: boolean | null;
  evidence_type?: string;
  has_reactions?: boolean | null;
  reaction_type?: string;
  reacted_by_me?: boolean | null;
  modified?: boolean | null;
  filter_operator?: "AND" | "OR";
  limit?: number;
  offset?: number;
};

export type ProjectActivityListResponse = {
  project_id: number;
  total: number;
  count: number;
  limit: number;
  offset: number;
  has_more: boolean;
  items: ProjectRecentActivity[];
  available_tags: string[];
};

export type ContributionFeedbackReview = {
  id: number;
  request_type: string;
  request_status: string;
  ai_impact_mode: string;
  content: string;
  resolution_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  author: {
    id: number;
    name: string;
    profile_image_url?: string | null;
  } | null;
  target_user: {
    id: number;
    name: string;
    profile_image_url?: string | null;
  } | null;
  contribution_result_id: number | null;
};

export type ContributionResult = {
  id: number;
  target_user: {
    id: number;
    name: string;
    profile_image_url?: string | null;
  } | null;
  reference_score: number;
  confidence_score: number;
  result_status: string;
  execution_score: number;
  collaboration_score: number;
  documentation_score: number;
  problem_solving_score: number;
  disputed_activity_count: number;
  down_weighted_activity_count: number;
  summary: string;
  rationale: string;
  public_explanation: string;
  uncertainty_note: string;
  warning_note: string;
  created_at: string;
  feedback_reviews: ContributionFeedbackReview[];
};

export type ContributionAnalysis = {
  id: number;
  project_id: number;
  requested_by_user_id: number;
  analysis_start_date: string;
  analysis_end_date: string;
  model_name: string;
  prompt_version: string;
  policy_version: string;
  analysis_mode: string;
  snapshot_at: string;
  status: string;
  input_summary: string;
  disclaimer: string;
  created_at: string;
  completed_at: string | null;
  results: ContributionResult[];
};

export type ContributionStaleSummary = {
  needs_reassessment: boolean;
  reason: string;
  changed_activity_count: number;
  days_since_latest_analysis: number | null;
  open_dispute_count: number;
};

export type ContributionLatestResponse = {
  analysis: ContributionAnalysis | null;
  active_analysis: ContributionAnalysis | null;
  can_assess: boolean;
  is_leader: boolean;
  has_my_pending_assessment: boolean;
  my_user_id: number;
  stale: ContributionStaleSummary;
  open_feedback_reviews: ContributionFeedbackReview[];
  recent_feedback_reviews: ContributionFeedbackReview[];
};

export type ContributionEventMessage = {
  type: "snapshot" | "queued" | "processing" | "completed" | "failed";
  event: {
    type: string;
    project_id: number;
    analysis_id: number | null;
    status: string | null;
    message?: string | null;
  } | null;
  payload: ContributionLatestResponse;
};

export type CreateProjectWorkItemPayload = {
  title: string;
  description: string;
  status: "TODO" | "IN_PROGRESS" | "DONE";
  priority: "LOW" | "MEDIUM" | "HIGH";
  assignee_user_id: number | null;
  parent_work_item_id?: number | null;
  gantt_sort_order?: number;
  timeline_start_date: string;
  timeline_end_date: string;
  attachment_file_ids?: number[];
};

export type UpdateProjectWorkItemPayload = Partial<CreateProjectWorkItemPayload>;

export type UpdateProjectWorkItemHierarchyPayload = {
  items: {
    work_item_id: number;
    parent_work_item_id: number | null;
    gantt_sort_order: number;
  }[];
};

export type WorkItemMutationResponse = {
  message: string;
  item: ProjectWorkItemSummary;
};

export type CreateProjectWorkItemDependencyPayload = {
  predecessor_work_item_id: number;
  successor_work_item_id: number;
};

export type WorkItemDependencyMutationResponse = {
  message: string;
  dependency: ProjectWorkItemDependency;
};

export type CreateProjectPayload = {
  title: string;
  description: string;
  start_date: string;
  end_date: string;
  join_policy: "AUTO_APPROVE" | "LEADER_APPROVE";  status?: string;};

export type UpdateProjectPayload = Partial<CreateProjectPayload> & {
  status?: string;
};

export type CreateProjectResponse = {
  message: string;
  project: ProjectSummary;
};

export type JoinPreviewResponse = {
  project: {
    id: number;
    title: string;
    description: string;
    status: string;
    start_date: string;
    end_date: string;
    join_policy: string;
    member_count: number;
  };
  already_member: boolean;
};

export type JoinProjectPayload = {
  join_code: string;
  request_message?: string;
  requested_position_label?: string;
};

export type JoinProjectResponse = {
  message: string;
  membership_created: boolean;
  project: {
    id: number;
    title: string;
    status: string;
    join_policy: string;
  };
  join_request: {
    id: number;
    project_id: number;
    request_status: string;
    requested_position_label: string | null;
    reviewed_project_role: string | null;
    reviewed_position_label: string | null;
  };
};
