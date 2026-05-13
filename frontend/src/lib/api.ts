import { navigate } from "./router";

const backendBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8028";
const refreshPath = "/api/auth/refresh";

type ApiRequestInit = RequestInit & {
  skipAuthRefresh?: boolean;
  skipErrorRedirect?: boolean;
};

let refreshPromise: Promise<boolean> | null = null;

export function getApiBaseUrl(): string {
  return backendBaseUrl;
}

export function getApiWebSocketBaseUrl(): string {
  if (backendBaseUrl.startsWith("https://")) {
    return `wss://${backendBaseUrl.slice("https://".length)}`;
  }
  if (backendBaseUrl.startsWith("http://")) {
    return `ws://${backendBaseUrl.slice("http://".length)}`;
  }
  return backendBaseUrl;
}

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function getErrorMessage(payload: unknown): string {
  if (typeof payload === "string" && payload.trim().length > 0) {
    return payload;
  }

  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  return "요청을 처리하지 못했습니다.";
}

async function parseResponsePayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

function moveToErrorPage(code: string, message: string): void {
  const params = new URLSearchParams({ code, message });
  if (window.location.pathname === "/error" && window.location.search === `?${params.toString()}`) {
    return;
  }
  navigate(`/error?${params.toString()}`);
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${backendBaseUrl}${refreshPath}`, {
      method: "POST",
      credentials: "include",
    })
      .then((response) => response.ok)
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

export async function apiRequest<T>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const {
    skipAuthRefresh = false,
    skipErrorRedirect = false,
    ...requestInit
  } = init;
  const headers = new Headers(requestInit.headers);

  try {
    const response = await fetch(`${backendBaseUrl}${path}`, {
      credentials: "include",
      ...requestInit,
      headers,
    });
    const payload = await parseResponsePayload(response);

    if (!response.ok) {
      if (response.status === 401 && !skipAuthRefresh && path !== refreshPath) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          return apiRequest<T>(path, {
            ...requestInit,
            skipAuthRefresh: true,
            skipErrorRedirect,
          });
        }

        if (!skipErrorRedirect) {
          moveToErrorPage(
            "401",
            "세션이 만료되었거나 다른 기기에서 로그인되어 로그아웃되었습니다.",
          );
        }
      } else if (response.status >= 500 && !skipErrorRedirect) {
        moveToErrorPage(
          String(response.status),
          "서버에서 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        );
      }

      throw new ApiError(response.status, getErrorMessage(payload), payload);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (!skipErrorRedirect) {
      moveToErrorPage(
        "network",
        "서버에 연결하지 못했습니다. 네트워크 또는 서버 상태를 확인해 주세요.",
      );
    }

    throw error;
  }
}

export function apiJsonRequest<T>(
  path: string,
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  body: unknown,
): Promise<T> {
  return apiRequest<T>(path, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export function getGoogleLoginUrl(): string {
  return `${backendBaseUrl}/api/auth/google/login`;
}

export function logout(): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
  });
}
