export type ChatUserSummary = {
  id: number;
  name: string;
  email?: string;
  profile_image_url?: string | null;
};

export type ChatUploadedFile = {
  id: number;
  file_name: string;
  content_type: string;
  file_size_bytes: number;
  is_image: boolean;
  download_url: string | null;
  preview_url: string | null;
  created_at: string | null;
  expires_at: string | null;
  is_expired: boolean;
};

export type ChatMessage = {
  id: number;
  room_id: number;
  message_type: "TEXT" | "IMAGE" | "FILE";
  content: string;
  created_at: string | null;
  attachment_expires_at: string | null;
  sender: ChatUserSummary | null;
  uploaded_file: ChatUploadedFile | null;
  unread_count: number;
};

export type ChatRoom = {
  id: number;
  project: {
    id: number;
    title: string;
  };
  room_type: "GROUP" | "DIRECT";
  title: string;
  member_count: number;
  participants: (ChatUserSummary | null)[];
  unread_count: number;
  last_message: ChatMessage | null;
  last_message_at: string | null;
  updated_at: string | null;
};

export type ChatRoomsResponse = {
  current_user: ChatUserSummary | null;
  rooms: ChatRoom[];
  total_unread_count: number;
};

export type ChatMessagesResponse = {
  room_id: number;
  messages: ChatMessage[];
  has_more: boolean;
};

export type ChatMessageCreatedEvent = {
  type: "message_created";
  room_id: number;
  project_id: number;
  message: ChatMessage;
};

export type ChatMessageUnreadCount = {
  message_id: number;
  unread_count: number;
};

export type ChatRoomReadUpdatedEvent = {
  type: "room_read_updated";
  room_id: number;
  project_id: number;
  reader_user_id: number;
  unread_counts: ChatMessageUnreadCount[];
};

export type ChatConnectedEvent = {
  type: "chat_connected";
  occurred_at: string;
};

export type ChatSocketEvent = ChatMessageCreatedEvent | ChatRoomReadUpdatedEvent | ChatConnectedEvent;
