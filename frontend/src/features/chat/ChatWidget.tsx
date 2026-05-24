import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError } from "../../lib/api";
import {
  deleteChatUpload,
  fetchChatMessages,
  fetchChatRooms,
  getChatWebSocketUrl,
  markChatRoomRead,
  prepareChatUploads,
  sendChatMessage,
  uploadPreparedChatFile,
} from "./api";
import type { ChatMessage, ChatRoom, ChatSocketEvent, ChatUploadedFile, ChatUserSummary } from "./types";

const CHAT_PANEL_MIN_WIDTH = 360;
const CHAT_PANEL_MIN_HEIGHT = 420;
const CHAT_PANEL_DEFAULT_WIDTH = 760;
const CHAT_PANEL_DEFAULT_HEIGHT = 620;
const CHAT_ATTACHMENT_MAX_TOTAL_BYTES = 50 * 1024 * 1024;
const CHAT_MESSAGE_PAGE_SIZE = 50;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function formatChatTime(value: string | null): string {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  });
}

function formatChatDateTime(value: string | null): string {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleString("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  });
}

function buildInitials(name: string | undefined): string {
  return name?.slice(0, 1).toUpperCase() || "N";
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }
  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)}KB`;
  }
  return `${bytes}B`;
}

function sortRooms(rooms: ChatRoom[]): ChatRoom[] {
  return [...rooms].sort((first, second) => {
    const firstTime = first.last_message_at || first.updated_at || "";
    const secondTime = second.last_message_at || second.updated_at || "";
    return secondTime.localeCompare(firstTime);
  });
}

function upsertMessage(messages: ChatMessage[], message: ChatMessage): ChatMessage[] {
  if (messages.some((item) => item.id === message.id)) {
    return messages.map((item) =>
      item.id === message.id
        ? { ...item, ...message, unread_count: Math.min(item.unread_count, message.unread_count) }
        : item,
    );
  }
  return [...messages, message];
}

function updateMessageUnreadCounts(
  messages: ChatMessage[],
  unreadCounts: { message_id: number; unread_count: number }[],
): ChatMessage[] {
  if (!unreadCounts.length) {
    return messages;
  }

  const unreadCountByMessageId = new Map(
    unreadCounts.map((item) => [item.message_id, item.unread_count]),
  );
  return messages.map((message) => {
    const unreadCount = unreadCountByMessageId.get(message.id);
    if (unreadCount === undefined) {
      return message;
    }

    return {
      ...message,
      unread_count: Math.min(message.unread_count, unreadCount),
    };
  });
}

function mergeMessages(messages: ChatMessage[]): ChatMessage[] {
  const messageById = new Map<number, ChatMessage>();
  messages.forEach((message) => {
    const previous = messageById.get(message.id);
    messageById.set(
      message.id,
      previous
        ? { ...previous, ...message, unread_count: Math.min(previous.unread_count, message.unread_count) }
        : message,
    );
  });
  return Array.from(messageById.values()).sort((first, second) => first.id - second.id);
}

function isNearMessageListBottom(element: HTMLDivElement): boolean {
  return element.scrollHeight - element.scrollTop - element.clientHeight < 120;
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="chat-float-icon">
      <path d="M4.8 5.6C4.8 4.2 5.9 3 7.4 3h9.2c1.5 0 2.6 1.2 2.6 2.6v6.7c0 1.5-1.1 2.6-2.6 2.6h-4.3l-4.1 3.6c-.5.4-1.2.1-1.2-.5v-3.1c-1.3-.2-2.2-1.3-2.2-2.6V5.6Z" />
    </svg>
  );
}

function renderChatMessageBody(
  message: ChatMessage,
  onPreviewImage: (file: ChatUploadedFile) => void,
) {
  const file = message.uploaded_file;
  const isAttachmentExpired = message.message_type !== "TEXT" && (!file || file.is_expired);

  if (isAttachmentExpired) {
    return (
      <p className="chat-attachment-expired">
        {message.message_type === "IMAGE" ? "삭제된 이미지입니다." : "삭제된 파일입니다."}
      </p>
    );
  }

  if (message.message_type === "IMAGE" && file?.preview_url) {
    return (
      <div className="chat-attachment-image-card">
        <button
          type="button"
          className="chat-attachment-image-preview"
          onClick={() => onPreviewImage(file)}
          title="이미지 원본 보기"
        >
          <img src={file.preview_url} alt={file.file_name} />
        </button>
        <small>이미지는 5일간만 보관됩니다.</small>
      </div>
    );
  }

  if (message.message_type === "FILE" && file?.download_url) {
    return (
      <a className="chat-attachment-file-link" href={file.download_url}>
        <span>{file.file_name}</span>
        <small>{formatFileSize(file.file_size_bytes)} · 5일간만 보관됩니다.</small>
      </a>
    );
  }

  if (message.message_type !== "TEXT") {
    return <p className="chat-attachment-expired">첨부 파일을 불러오지 못했습니다.</p>;
  }

  return <p>{message.content}</p>;
}

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [currentUser, setCurrentUser] = useState<ChatUserSummary | null>(null);
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);
  const [messagesByRoom, setMessagesByRoom] = useState<Record<number, ChatMessage[]>>({});
  const [hasMoreMessagesByRoom, setHasMoreMessagesByRoom] = useState<Record<number, boolean>>({});
  const [loadingOlderRoomId, setLoadingOlderRoomId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [isLoadingRooms, setIsLoadingRooms] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [previewFile, setPreviewFile] = useState<ChatUploadedFile | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUnavailable, setIsUnavailable] = useState(false);
  const [socketRetryKey, setSocketRetryKey] = useState(0);
  const [panelSize, setPanelSize] = useState({
    width: CHAT_PANEL_DEFAULT_WIDTH,
    height: CHAT_PANEL_DEFAULT_HEIGHT,
  });

  const selectedRoomIdRef = useRef<number | null>(selectedRoomId);
  const roomsRef = useRef<ChatRoom[]>(rooms);
  const isOpenRef = useRef(isOpen);
  const currentUserIdRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pendingScrollRef = useRef<
    | { type: "bottom" }
    | { type: "preserve"; previousScrollHeight: number; previousScrollTop: number }
    | null
  >(null);

  const totalUnreadCount = useMemo(
    () => rooms.reduce((total, room) => total + room.unread_count, 0),
    [rooms],
  );
  const currentUserId = currentUser?.id ?? null;
  const selectedRoom = rooms.find((room) => room.id === selectedRoomId) ?? null;
  const selectedMessages = selectedRoomId ? messagesByRoom[selectedRoomId] ?? [] : [];

  useEffect(() => {
    selectedRoomIdRef.current = selectedRoomId;
  }, [selectedRoomId]);

  useEffect(() => {
    roomsRef.current = rooms;
  }, [rooms]);

  useEffect(() => {
    isOpenRef.current = isOpen;
  }, [isOpen]);

  useEffect(() => {
    currentUserIdRef.current = currentUserId;
  }, [currentUserId]);

  useEffect(() => {
    if (!isOpen || !messageListRef.current || !pendingScrollRef.current) {
      return;
    }

    const pendingScroll = pendingScrollRef.current;
    pendingScrollRef.current = null;
    window.requestAnimationFrame(() => {
      const element = messageListRef.current;
      if (!element) {
        return;
      }

      if (pendingScroll.type === "bottom") {
        element.scrollTop = element.scrollHeight;
        return;
      }

      element.scrollTop = element.scrollHeight - pendingScroll.previousScrollHeight + pendingScroll.previousScrollTop;
    });
  }, [isLoadingMessages, isOpen, loadingOlderRoomId, selectedRoomId, selectedMessages.length]);

  const updateRoomReadState = useCallback((roomId: number, unreadCount: number) => {
    setRooms((previous) =>
      previous.map((room) =>
        room.id === roomId ? { ...room, unread_count: unreadCount } : room,
      ),
    );
  }, []);

  const markSelectedRoomRead = useCallback((roomId: number) => {
    updateRoomReadState(roomId, 0);
    void markChatRoomRead(roomId).catch(() => {
      // 읽음 처리는 다음 목록 조회 때 복구된다.
    });
  }, [updateRoomReadState]);

  const loadRooms = useCallback(async () => {
    setIsLoadingRooms(true);
    setErrorMessage(null);
    try {
      const response = await fetchChatRooms();
      const roomToReadId = isOpenRef.current
        ? selectedRoomIdRef.current ?? response.rooms[0]?.id ?? null
        : null;
      const nextRooms = sortRooms(
        response.rooms.map((room) =>
          room.id === roomToReadId ? { ...room, unread_count: 0 } : room,
        ),
      );
      setRooms(nextRooms);
      setCurrentUser(response.current_user);
      setIsUnavailable(false);
      setSelectedRoomId((previous) => {
        if (previous && nextRooms.some((room) => room.id === previous)) {
          return previous;
        }
        return nextRooms[0]?.id ?? null;
      });
      if (roomToReadId) {
        void markChatRoomRead(roomToReadId).catch(() => {
          // 다음 목록 조회 때 다시 맞춰진다.
        });
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setIsUnavailable(true);
        return;
      }
      setErrorMessage("채팅방을 불러오지 못했습니다.");
    } finally {
      setIsLoadingRooms(false);
    }
  }, []);

  useEffect(() => {
    void loadRooms();
  }, [loadRooms]);

  useEffect(() => {
    if (currentUserId === null) {
      return;
    }

    let isIntentionalClose = false;
    const socket = new WebSocket(getChatWebSocketUrl());

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ChatSocketEvent;
        if (data.type === "room_read_updated") {
          setMessagesByRoom((previous) => ({
            ...previous,
            [data.room_id]: updateMessageUnreadCounts(
              previous[data.room_id] ?? [],
              data.unread_counts,
            ),
          }));
          return;
        }

        if (data.type !== "message_created") {
          return;
        }

        const { room_id: roomId, message } = data;
        const senderId = message.sender?.id ?? null;
        const isOwnMessage = senderId === currentUserIdRef.current;
        const activeRoomId = selectedRoomIdRef.current ?? (roomsRef.current.length === 1 ? roomsRef.current[0].id : null);
        const isCurrentRoom = activeRoomId === roomId && isOpenRef.current;
        const messageList = messageListRef.current;
        if (isCurrentRoom && (isOwnMessage || !messageList || isNearMessageListBottom(messageList))) {
          pendingScrollRef.current = { type: "bottom" };
        }

        setMessagesByRoom((previous) => ({
          ...previous,
          [roomId]: upsertMessage(previous[roomId] ?? [], message),
        }));

        setRooms((previous) => {
          const hasRoom = previous.some((room) => room.id === roomId);
          if (!hasRoom) {
            void loadRooms();
            return previous;
          }

          return sortRooms(
            previous.map((room) => {
              if (room.id !== roomId) {
                return room;
              }

              return {
                ...room,
                last_message: message,
                last_message_at: message.created_at,
                unread_count: isCurrentRoom || isOwnMessage ? 0 : room.unread_count + 1,
              };
            }),
          );
        });

        if (isCurrentRoom) {
          markSelectedRoomRead(roomId);
        }
      } catch {
        // 잘못된 소켓 이벤트는 무시한다.
      }
    };

    socket.onclose = (event) => {
      if (isIntentionalClose || event.code === 4401 || event.code === 4403) {
        return;
      }
      reconnectTimerRef.current = window.setTimeout(() => {
        setSocketRetryKey((key) => key + 1);
      }, 3000);
    };

    return () => {
      isIntentionalClose = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      socket.close();
    };
  }, [currentUserId, loadRooms, markSelectedRoomRead, socketRetryKey]);

  useEffect(() => {
    if (!isOpen || !selectedRoomId) {
      return;
    }

    setIsLoadingMessages(true);
    setErrorMessage(null);
    fetchChatMessages(selectedRoomId, { limit: CHAT_MESSAGE_PAGE_SIZE })
      .then((response) => {
        pendingScrollRef.current = { type: "bottom" };
        setMessagesByRoom((previous) => ({
          ...previous,
          [selectedRoomId]: mergeMessages(response.messages),
        }));
        setHasMoreMessagesByRoom((previous) => ({
          ...previous,
          [selectedRoomId]: response.has_more,
        }));
        markSelectedRoomRead(selectedRoomId);
      })
      .catch(() => {
        setErrorMessage("메시지를 불러오지 못했습니다.");
      })
      .finally(() => {
        setIsLoadingMessages(false);
      });
  }, [isOpen, markSelectedRoomRead, selectedRoomId]);

  const loadOlderMessages = async (roomId: number, listElement: HTMLDivElement) => {
    if (loadingOlderRoomId === roomId || !hasMoreMessagesByRoom[roomId]) {
      return;
    }

    const currentMessages = messagesByRoom[roomId] ?? [];
    const firstMessage = currentMessages[0];
    if (!firstMessage) {
      return;
    }

    const previousScrollHeight = listElement.scrollHeight;
    const previousScrollTop = listElement.scrollTop;
    setLoadingOlderRoomId(roomId);
    setErrorMessage(null);

    try {
      const response = await fetchChatMessages(roomId, {
        beforeId: firstMessage.id,
        limit: CHAT_MESSAGE_PAGE_SIZE,
      });
      pendingScrollRef.current = {
        type: "preserve",
        previousScrollHeight,
        previousScrollTop,
      };
      setMessagesByRoom((previous) => ({
        ...previous,
        [roomId]: mergeMessages([
          ...response.messages,
          ...(previous[roomId] ?? []),
        ]),
      }));
      setHasMoreMessagesByRoom((previous) => ({
        ...previous,
        [roomId]: response.has_more,
      }));
    } catch {
      setErrorMessage("이전 메시지를 불러오지 못했습니다.");
    } finally {
      setLoadingOlderRoomId(null);
    }
  };

  const handleMessageListScroll = (event: React.UIEvent<HTMLDivElement>) => {
    if (!selectedRoomId || event.currentTarget.scrollTop > 48) {
      return;
    }
    void loadOlderMessages(selectedRoomId, event.currentTarget);
  };

  const handleToggleOpen = () => {
    setIsOpen((previous) => {
      const next = !previous;
      if (next) {
        void loadRooms();
      }
      return next;
    });
  };

  const handleResizePointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const startX = event.clientX;
    const startY = event.clientY;
    const startWidth = panelSize.width;
    const startHeight = panelSize.height;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.userSelect = "none";

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const maxWidth = Math.max(CHAT_PANEL_MIN_WIDTH, window.innerWidth - 32);
      const maxHeight = Math.max(CHAT_PANEL_MIN_HEIGHT, window.innerHeight - 120);
      setPanelSize({
        width: clamp(startWidth + startX - moveEvent.clientX, CHAT_PANEL_MIN_WIDTH, maxWidth),
        height: clamp(startHeight + startY - moveEvent.clientY, CHAT_PANEL_MIN_HEIGHT, maxHeight),
      });
    };

    const handlePointerUp = () => {
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp, { once: true });
  };

  const applySentMessage = useCallback((roomId: number, message: ChatMessage) => {
    pendingScrollRef.current = { type: "bottom" };
    setMessagesByRoom((previous) => ({
      ...previous,
      [roomId]: upsertMessage(previous[roomId] ?? [], message),
    }));
    setRooms((previous) =>
      sortRooms(
        previous.map((room) =>
          room.id === roomId
            ? {
                ...room,
                last_message: message,
                last_message_at: message.created_at,
                unread_count: 0,
              }
            : room,
        ),
      ),
    );
    markSelectedRoomRead(roomId);
  }, [markSelectedRoomRead]);

  const handleSendMessage = async () => {
    if (!selectedRoomId || isSending || isUploadingAttachment) {
      return;
    }

    const content = draft.trim();
    if (!content) {
      return;
    }

    setIsSending(true);
    setErrorMessage(null);
    try {
      const response = await sendChatMessage(selectedRoomId, content);
      setDraft("");
      applySentMessage(selectedRoomId, response.message);
    } catch {
      setErrorMessage("메시지를 보내지 못했습니다.");
    } finally {
      setIsSending(false);
    }
  };

  const handleAttachmentFiles = async (fileList: FileList | null) => {
    if (!selectedRoomId || isUploadingAttachment || isSending) {
      return;
    }

    const roomId = selectedRoomId;
    const files = Array.from(fileList ?? []);
    if (files.length === 0) {
      return;
    }

    const totalSize = files.reduce((sum, file) => sum + file.size, 0);
    if (totalSize > CHAT_ATTACHMENT_MAX_TOTAL_BYTES) {
      setErrorMessage("첨부 파일 전체 용량은 50MB를 넘을 수 없습니다.");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    setIsUploadingAttachment(true);
    setErrorMessage(null);
    let preparedFileIds: number[] = [];
    const sentFileIds = new Set<number>();
    try {
      const prepared = await prepareChatUploads(
        roomId,
        files.map((file) => ({
          file_name: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
        })),
      );
      preparedFileIds = prepared.items.map((upload) => upload.id);

      await Promise.all(prepared.items.map((upload, index) => uploadPreparedChatFile(upload, files[index])));

      for (const upload of prepared.items) {
        const response = await sendChatMessage(roomId, {
          content: upload.file_name,
          message_type: upload.is_image ? "IMAGE" : "FILE",
          uploaded_file_id: upload.id,
        });
        sentFileIds.add(upload.id);
        applySentMessage(roomId, response.message);
      }
    } catch (error) {
      const unsentFileIds = preparedFileIds.filter((fileId) => !sentFileIds.has(fileId));
      await Promise.allSettled(unsentFileIds.map((fileId) => deleteChatUpload(roomId, fileId)));
      setErrorMessage(error instanceof Error ? error.message : "첨부 파일을 보내지 못했습니다.");
    } finally {
      setIsUploadingAttachment(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSendMessage();
    }
  };

  if (isUnavailable) {
    return null;
  }

  return (
    <div className="chat-widget" aria-live="polite">
      {isOpen ? (
        <section
          className="chat-panel"
          aria-label="프로젝트 채팅"
          style={{
            "--chat-panel-width": `${panelSize.width}px`,
            "--chat-panel-height": `${panelSize.height}px`,
          } as React.CSSProperties}
        >
          <button
            type="button"
            className="chat-resize-handle"
            onPointerDown={handleResizePointerDown}
            aria-label="채팅창 크기 조절"
            title="채팅창 크기 조절"
          />
          <header className="chat-panel-header">
            <div>
              <strong>프로젝트 채팅</strong>
              <span>{rooms.length ? `${rooms.length}개 채팅방` : "채팅방 없음"}</span>
            </div>
            <button type="button" onClick={() => setIsOpen(false)} aria-label="채팅 닫기">
              닫기
            </button>
          </header>

          <div className="chat-panel-body">
            <aside className="chat-room-list" aria-label="채팅방 목록">
              {isLoadingRooms ? (
                <div className="chat-empty-state">불러오는 중</div>
              ) : rooms.length ? (
                rooms.map((room) => (
                  <button
                    type="button"
                    key={room.id}
                    className={`chat-room-item ${room.id === selectedRoomId ? "active" : ""}`}
                    onClick={() => setSelectedRoomId(room.id)}
                  >
                    <span className="chat-room-title">{room.project.title}</span>
                    <span className="chat-room-preview">
                      {room.last_message?.content || `${room.member_count}명 참여 중`}
                    </span>
                    {room.unread_count > 0 ? (
                      <span className="chat-room-unread">{room.unread_count}</span>
                    ) : null}
                  </button>
                ))
              ) : (
                <div className="chat-empty-state">참여 중인 프로젝트 채팅방이 없습니다.</div>
              )}
            </aside>

            <main className="chat-conversation">
              {selectedRoom ? (
                <>
                  <div className="chat-conversation-header">
                    <div>
                      <strong>{selectedRoom.project.title}</strong>
                      <span>{selectedRoom.member_count}명</span>
                    </div>
                    <small>{selectedRoom.last_message_at ? formatChatDateTime(selectedRoom.last_message_at) : ""}</small>
                  </div>

                  <div className="chat-message-list" ref={messageListRef} onScroll={handleMessageListScroll}>
                    {isLoadingMessages ? (
                      <div className="chat-empty-state">메시지를 불러오는 중</div>
                    ) : selectedMessages.length ? (
                      <>
                        {loadingOlderRoomId === selectedRoomId ? (
                          <div className="chat-older-loading">이전 메시지를 불러오는 중</div>
                        ) : null}
                        {selectedMessages.map((message) => {
                        const isMine = message.sender?.id === currentUser?.id;
                        return (
                          <article
                            key={message.id}
                            className={`chat-message ${isMine ? "mine" : ""}`}
                          >
                            {!isMine ? (
                              <div className="chat-message-avatar">
                                {message.sender?.profile_image_url ? (
                                  <img src={message.sender.profile_image_url} alt="" />
                                ) : (
                                  <span>{buildInitials(message.sender?.name)}</span>
                                )}
                              </div>
                            ) : null}
                            <div className="chat-message-content">
                              {!isMine ? <strong>{message.sender?.name || "알 수 없음"}</strong> : null}
                              <div className="chat-message-bubble-row">
                                {renderChatMessageBody(message, setPreviewFile)}
                                {message.unread_count > 0 ? (
                                  <span
                                    className="chat-message-unread-count"
                                    title={`${message.unread_count}명이 아직 읽지 않음`}
                                  >
                                    {message.unread_count}
                                  </span>
                                ) : null}
                              </div>
                              <div className="chat-message-meta">
                                <time>{formatChatTime(message.created_at)}</time>
                              </div>
                            </div>
                          </article>
                        );
                        })}
                      </>
                    ) : (
                      <div className="chat-empty-state">아직 메시지가 없습니다.</div>
                    )}
                  </div>

                  <footer className="chat-composer">
                    <input
                      ref={fileInputRef}
                      className="chat-file-input"
                      type="file"
                      multiple
                      onChange={(event) => void handleAttachmentFiles(event.target.files)}
                      disabled={isUploadingAttachment || isSending}
                    />
                    <button
                      type="button"
                      className="chat-attach-button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploadingAttachment || isSending}
                      aria-label="파일 첨부"
                      title="파일 첨부"
                    >
                      +
                    </button>
                    <textarea
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={handleComposerKeyDown}
                      placeholder={isUploadingAttachment ? "첨부 파일 업로드 중..." : "메시지를 입력하세요"}
                      maxLength={2000}
                      disabled={isUploadingAttachment}
                    />
                    <button
                      type="button"
                      onClick={() => void handleSendMessage()}
                      disabled={isSending || isUploadingAttachment || !draft.trim()}
                    >
                      전송
                    </button>
                  </footer>
                </>
              ) : (
                <div className="chat-empty-state wide">채팅방을 선택하세요.</div>
              )}
            </main>
          </div>

          {errorMessage ? <div className="chat-error-message">{errorMessage}</div> : null}
        </section>
      ) : null}

      {previewFile?.preview_url ? createPortal(
        <div className="image-preview-backdrop" onClick={() => setPreviewFile(null)}>
          <div className="image-preview-modal" onClick={(event) => event.stopPropagation()}>
            <button type="button" className="image-preview-close" onClick={() => setPreviewFile(null)}>
              닫기
            </button>
            <img src={previewFile.preview_url} alt={previewFile.file_name} />
            <div className="image-preview-footer">
              <span>{previewFile.file_name}</span>
              {previewFile.download_url ? (
                <a href={previewFile.download_url}>다운로드</a>
              ) : null}
            </div>
          </div>
        </div>,
        document.body,
      ) : null}

      <button
        type="button"
        className="chat-float-button"
        onClick={handleToggleOpen}
        aria-label="채팅 열기"
      >
        <ChatIcon />
        {totalUnreadCount > 0 ? (
          <span className="chat-float-badge">{totalUnreadCount > 99 ? "99+" : totalUnreadCount}</span>
        ) : null}
      </button>
    </div>
  );
}
