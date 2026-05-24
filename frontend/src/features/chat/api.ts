import { apiRequest, getApiWebSocketBaseUrl } from "../../lib/api";
import type { ChatMessage, ChatMessagesResponse, ChatRoomsResponse, ChatUploadedFile } from "./types";

export function fetchChatRooms(): Promise<ChatRoomsResponse> {
  return apiRequest<ChatRoomsResponse>("/api/chats/rooms", { skipErrorRedirect: true });
}

export function fetchChatMessages(
  roomId: number,
  options: { beforeId?: number; limit?: number } = {},
): Promise<ChatMessagesResponse> {
  const params = new URLSearchParams();
  if (options.beforeId !== undefined) {
    params.set("before_id", String(options.beforeId));
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  const query = params.toString();
  return apiRequest<ChatMessagesResponse>(
    `/api/chats/rooms/${roomId}/messages${query ? `?${query}` : ""}`,
    {
      skipErrorRedirect: true,
    },
  );
}

export type SendChatMessagePayload = {
  content: string;
  message_type?: ChatMessage["message_type"];
  uploaded_file_id?: number | null;
};

export type PrepareChatUploadRequest = {
  file_name: string;
  content_type: string;
  size_bytes: number;
};

export type PreparedChatUpload = Pick<
  ChatUploadedFile,
  "id" | "file_name" | "content_type" | "file_size_bytes" | "is_image"
> & {
  upload_url: string;
  s3_object_key: string;
  retention_days: number;
};

export function sendChatMessage(
  roomId: number,
  payload: string | SendChatMessagePayload,
): Promise<{ message: ChatMessage }> {
  const body = typeof payload === "string" ? { content: payload } : payload;
  return apiRequest<{ message: ChatMessage }>(`/api/chats/rooms/${roomId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    skipErrorRedirect: true,
  });
}

export function prepareChatUploads(
  roomId: number,
  files: PrepareChatUploadRequest[],
): Promise<{ items: PreparedChatUpload[]; max_total_bytes: number; retention_days: number }> {
  return apiRequest<{ items: PreparedChatUpload[]; max_total_bytes: number; retention_days: number }>(
    `/api/chats/rooms/${roomId}/uploads/presign`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ files }),
      skipErrorRedirect: true,
    },
  );
}

export async function uploadPreparedChatFile(upload: PreparedChatUpload, file: File): Promise<void> {
  const response = await fetch(upload.upload_url, {
    method: "PUT",
    headers: {
      "Content-Type": upload.content_type,
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error(`${file.name} 업로드에 실패했습니다.`);
  }
}

export function deleteChatUpload(
  roomId: number,
  fileId: number,
): Promise<{ message: string; file_id: number }> {
  return apiRequest<{ message: string; file_id: number }>(
    `/api/chats/rooms/${roomId}/uploads/${fileId}`,
    { method: "DELETE", skipErrorRedirect: true },
  );
}

export function markChatRoomRead(roomId: number): Promise<{ room_id: number; unread_count: number }> {
  return apiRequest<{ room_id: number; unread_count: number }>(`/api/chats/rooms/${roomId}/read`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
    skipErrorRedirect: true,
  });
}

export function getChatWebSocketUrl(): string {
  return `${getApiWebSocketBaseUrl()}/api/chats/ws`;
}
