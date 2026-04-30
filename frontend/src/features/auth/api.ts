import { apiRequest } from "../../lib/api";
import type { AuthUser } from "./types";

export type CurrentUserResponse = {
  authenticated: boolean;
  user: AuthUser | null;
};

export function fetchCurrentUser(): Promise<CurrentUserResponse> {
  return apiRequest<CurrentUserResponse>("/api/auth/me");
}
