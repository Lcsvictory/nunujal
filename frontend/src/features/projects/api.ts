import { apiJsonRequest, apiRequest, getApiWebSocketBaseUrl } from "../../lib/api";
import type {
  CreateProjectWorkItemDependencyPayload,
  CreateProjectPayload,
  CreateProjectWorkItemPayload,
  CreateProjectResponse,
  JoinPreviewResponse,
  JoinProjectPayload,
  JoinProjectResponse,
  ProjectDetailResponse,
  ProjectListResponse,
  ProjectWorkItemListResponse,
  ProjectMemberSummary,
  UpdateProjectPayload,
  UpdateProjectWorkItemPayload,
  WorkItemDependencyMutationResponse,
  WorkItemMutationResponse,
} from "./types";

export function fetchProjects(): Promise<ProjectListResponse> {
  return apiRequest<ProjectListResponse>("/api/projects");
}

export function fetchProjectDetail(projectId: number): Promise<ProjectDetailResponse> {
  return apiRequest<ProjectDetailResponse>(`/api/projects/${projectId}`);
}

export function deleteProject(projectId: number): Promise<{ status: string; message: string }> {
  return apiRequest<{ status: string; message: string }>(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
}

export function fetchProjectWorkItems(projectId: number): Promise<ProjectWorkItemListResponse> {
  return apiRequest<ProjectWorkItemListResponse>(`/api/projects/${projectId}/work-items`);
}

export function createProjectWorkItem(
  projectId: number,
  payload: CreateProjectWorkItemPayload,
): Promise<WorkItemMutationResponse> {
  return apiJsonRequest<WorkItemMutationResponse>(
    `/api/projects/${projectId}/work-items`,
    "POST",
    payload,
  );
}

export function updateProjectWorkItem(
  projectId: number,
  workItemId: number,
  payload: UpdateProjectWorkItemPayload
): Promise<WorkItemMutationResponse> {
  return apiJsonRequest<WorkItemMutationResponse>(
    `/api/projects/${projectId}/work-items/${workItemId}`,
    "PATCH",
    payload,
  );
}

export function deleteProjectWorkItem(
  projectId: number,
  workItemId: number,
): Promise<{ message: string; work_item_id: number }> {
  return apiRequest<{ message: string; work_item_id: number }>(
    `/api/projects/${projectId}/work-items/${workItemId}`,
    { method: "DELETE" },
  );
}

export function createProjectWorkItemDependency(
  projectId: number,
  payload: CreateProjectWorkItemDependencyPayload,
): Promise<WorkItemDependencyMutationResponse> {
  return apiJsonRequest<WorkItemDependencyMutationResponse>(
    `/api/projects/${projectId}/work-item-dependencies`,
    "POST",
    payload,
  );
}

export function deleteProjectWorkItemDependency(
  projectId: number,
  dependencyId: number,
): Promise<{ message: string; dependency_id: number }> {
  return apiRequest<{ message: string; dependency_id: number }>(
    `/api/projects/${projectId}/work-item-dependencies/${dependencyId}`,
    { method: "DELETE" },
  );
}

export function getProjectWorkItemsWebSocketUrl(projectId: number): string {
  return `${getApiWebSocketBaseUrl()}/api/projects/${projectId}/work-items/ws`;
}

export function createProject(payload: CreateProjectPayload): Promise<CreateProjectResponse> {
  return apiJsonRequest<CreateProjectResponse>("/api/projects", "POST", payload);
}

export function updateProject(
  projectId: number,
  payload: UpdateProjectPayload,
): Promise<{ status: string; message: string; project_id: number; payload: object }> {
  return apiJsonRequest<{ status: string; message: string; project_id: number; payload: object }>(
    `/api/projects/${projectId}`,
    "PATCH",
    payload,
  );
}

export function previewProjectByJoinCode(joinCode: string): Promise<JoinPreviewResponse> {
  return apiRequest<JoinPreviewResponse>(`/api/projects/join-preview/${encodeURIComponent(joinCode.trim().toUpperCase())}`);
}

export function createProjectJoinRequest(
  payload: JoinProjectPayload,
): Promise<JoinProjectResponse> {
  return apiJsonRequest<JoinProjectResponse>("/api/project-join-requests", "POST", payload);
}

export function fetchProjectMembers(projectId: number): Promise<{ items: ProjectMemberSummary[] }> {
  return apiRequest<{ items: ProjectMemberSummary[] }>(`/api/projects/${projectId}/members`);
}

type ProjectJoinRequestItem = {
  id: number;
  project_id: number;
  requester_user_id: number;
  requester_name: string;
  requester_email: string;
  request_message: string;
  requested_position_label: string;
  request_status: string;
  created_at: string;
};

export function fetchProjectJoinRequests(projectId: number): Promise<{ items: ProjectJoinRequestItem[] }> {
  return apiRequest<{ items: ProjectJoinRequestItem[] }>(`/api/projects/${projectId}/join-requests`);
}

export type ReviewProjectJoinRequestPayload = {
  request_status: "APPROVED" | "REJECTED";
  reviewed_project_role?: "LEADER" | "MEMBER";
  reviewed_position_label?: string;
  review_note?: string;
};

export function reviewProjectJoinRequest(
  projectId: number,
  requestId: number,
  payload: ReviewProjectJoinRequestPayload
): Promise<{ status: string; message: string }> {
  return apiJsonRequest<{ status: string; message: string }>(
    `/api/projects/${projectId}/join-requests/${requestId}`,
    "PATCH",
    payload
  );
}

export async function toggleActivityReaction(
  projectId: number,
  activityId: number,
  reactionType: "CONFIRMED" | "HELPFUL" | "AWESOME"
) {
  return await apiJsonRequest(
    `/api/projects/${projectId}/activities/${activityId}/reactions`,
    "POST",
    { reaction_type: reactionType }
  );
}
