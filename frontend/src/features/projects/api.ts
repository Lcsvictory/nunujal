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
  payload: UpdateProjectWorkItemPayload,
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

export function previewProjectByJoinCode(joinCode: string): Promise<JoinPreviewResponse> {
  return apiRequest<JoinPreviewResponse>(`/api/projects/join-preview/${encodeURIComponent(joinCode.trim().toUpperCase())}`);
}

export function createProjectJoinRequest(
  payload: JoinProjectPayload,
): Promise<JoinProjectResponse> {
  return apiJsonRequest<JoinProjectResponse>("/api/project-join-requests", "POST", payload);
}
