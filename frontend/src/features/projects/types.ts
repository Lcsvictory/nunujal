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

export type ProjectMemberSummary = {
  project_member_id: number;
  user_id: number;
  name: string;
  email: string;
  project_role: string;
  position_label: string;
};

export type ProjectRecentActivity = {
  id: number;
  title: string;
  content: string;
  activity_category: string;
  activity_type: string;
  review_state: string;
  occurred_at: string;
  actor: {
    id: number;
    name: string;
  };
  target_user: {
    id: number;
    name: string;
  } | null;
  work_items: {
    id: number;
    title: string;
  }[];
  evidences?: any[];
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
  creator: {
    id: number;
    name: string;
  };
  assignee: {
    id: number;
    name: string;
  } | null;
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

export type CreateProjectWorkItemPayload = {
  title: string;
  description: string;
  status: "TODO" | "IN_PROGRESS" | "DONE";
  priority: "LOW" | "MEDIUM" | "HIGH";
  assignee_user_id: number | null;
  timeline_start_date: string;
  timeline_end_date: string;
};

export type UpdateProjectWorkItemPayload = Partial<CreateProjectWorkItemPayload>;

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
