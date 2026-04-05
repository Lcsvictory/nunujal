import { apiJsonRequest, apiRequest } from "../../lib/api";
import type {
  CreateProjectPayload,
  CreateProjectResponse,
  JoinPreviewResponse,
  JoinProjectPayload,
  JoinProjectResponse,
  ProjectDetailResponse,
  ProjectListResponse,
} from "./types";

export function fetchProjects(): Promise<ProjectListResponse> {
  return apiRequest<ProjectListResponse>("/api/projects");
}

export function fetchProjectDetail(projectId: number): Promise<ProjectDetailResponse> {
  return apiRequest<ProjectDetailResponse>(`/api/projects/${projectId}`);
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
