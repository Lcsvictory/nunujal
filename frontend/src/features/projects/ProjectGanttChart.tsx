import { useEffect, useMemo, useRef, useState } from "react";
import { gantt, type GanttStatic, type Link, type Task } from "dhtmlx-gantt";
import "dhtmlx-gantt/codebase/dhtmlxgantt.css";
import { ApiError } from "../../lib/api";
import {
  createProjectWorkItem,
  createProjectWorkItemDependency,
  deleteProjectWorkItem,
  deleteProjectWorkItemDependency,
  fetchProjectWorkItems,
  getProjectWorkItemsWebSocketUrl,
  updateProjectWorkItem,
} from "./api";
import { ProjectTaskCreateOverlay } from "./ProjectTaskCreateOverlay";
import { ProjectTaskEditOverlay } from "./ProjectTaskEditOverlay";
import type {
  CreateProjectWorkItemPayload,
  ProjectMemberSummary,
  ProjectWorkItemDependency,
  ProjectWorkItemSummary,
  UpdateProjectWorkItemPayload,
} from "./types";

type ProjectGanttChartProps = {
  projectId: number;
  startDate: string;
  endDate: string;
  projectMembers: ProjectMemberSummary[];
  isVisible: boolean;
};

type WorkItemStatus = "done" | "in_progress" | "planned";

type ChartWorkItem = {
  id: string;
  numericId: number;
  code: string;
  title: string;
  description: string;
  owner: string;
  creatorName: string;
  status: WorkItemStatus;
  priority: ProjectWorkItemSummary["priority"];
  priorityLabel: string;
  progress: number;
  startDate: string;
  endDate: string;
  durationDays: number;
  assigneeUserId: number | null;
  updatedAt: string;
};

type ChartWorkItemDependency = {
  id: string;
  numericId: number;
  predecessorWorkItemId: string;
  successorWorkItemId: string;
};

type DhtmlxTask = Task & {
  code: string;
  description: string;
  owner: string;
  assignee_user_id: string;
  status_code: WorkItemStatus;
  status_label: string;
  priority_code: ProjectWorkItemSummary["priority"];
  priority_label: string;
  creator_name: string;
  start_label: string;
  end_label: string;
  updated_label: string;
};

const STATUS_META: Record<
  WorkItemStatus,
  { label: string; barColor: string; progressColor: string }
> = {
  done: { label: "완료", barColor: "#2557ff", progressColor: "#1837a5" },
  in_progress: { label: "진행 중", barColor: "#0f87df", progressColor: "#0c5fa0" },
  planned: { label: "예정", barColor: "#7d8aa5", progressColor: "#5b6884" },
};

const PRIORITY_LABELS: Record<ProjectWorkItemSummary["priority"], string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

const ZOOM_LEVELS = [
  { name: "좁게", min_column_width: 34 },
  { name: "기본", min_column_width: 48 },
  { name: "넓게", min_column_width: 64 },
] as const;

function parseLocalDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

function addDays(date: Date, amount: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + amount);
}

function differenceInDays(later: Date, earlier: Date): number {
  return Math.round((startOfDay(later).getTime() - startOfDay(earlier).getTime()) / 86400000);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function toLocalIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateLabel(value: string): string {
  const date = parseLocalDate(value);
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}.${month}.${day}`;
}

function formatDateTimeLabel(value: string): string {
  const date = new Date(value);
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatMonthScale(date: Date): string {
  if (date.getMonth() === 0) {
    return `${date.getFullYear()}년 ${date.getMonth() + 1}월`;
  }
  return `${date.getMonth() + 1}월`;
}

function centerTimelineOnDate(ganttInstance: GanttStatic, date: Date) {
  const timelineArea = ganttInstance.$task as HTMLElement | undefined;
  if (!timelineArea) {
    return;
  }

  const { y } = ganttInstance.getScrollState();
  const targetX = ganttInstance.posFromDate(date) - timelineArea.clientWidth / 2;
  console.log(`Centering timeline on ${date.toISOString().split("T")[0]} at x=${targetX}, y=${y}`);
  ganttInstance.scrollTo(Math.max(targetX, 0), y);
}

function isDateVisible(ganttInstance: GanttStatic, date: Date): boolean {
  const timelineArea = ganttInstance.$task as HTMLElement | undefined;
  if (!timelineArea) {
    return false;
  }

  const { x } = ganttInstance.getScrollState();
  const targetX = ganttInstance.posFromDate(date);
  return targetX >= x && targetX <= x + timelineArea.clientWidth;
}

function getWorkItemStatus(status: ProjectWorkItemSummary["status"]): WorkItemStatus {
  if (status === "DONE") {
    return "done";
  }
  if (status === "IN_PROGRESS") {
    return "in_progress";
  }
  return "planned";
}

function buildProgress(item: ProjectWorkItemSummary, startDate: string, endDate: string): number {
  if (item.status === "DONE") {
    return 100;
  }
  if (item.status === "TODO") {
    return 0;
  }

  const start = parseLocalDate(startDate);
  const end = parseLocalDate(endDate);
  const totalDays = Math.max(differenceInDays(end, start) + 1, 1);
  const elapsedDays = clamp(differenceInDays(startOfDay(new Date()), start) + 1, 1, totalDays);
  return clamp(Math.round((elapsedDays / totalDays) * 100), 10, 95);
}

function toChartWorkItem(item: ProjectWorkItemSummary): ChartWorkItem {
  const startDate = item.timeline_start_date;
  const endDate = item.timeline_end_date;

  return {
    id: String(item.id),
    numericId: item.id,
    code: `WI-${String(item.id).padStart(3, "0")}`,
    title: item.title,
    description: item.description.trim() || "설명이 아직 없습니다.",
    owner: item.assignee?.name ?? item.creator.name,
    creatorName: item.creator.name,
    status: getWorkItemStatus(item.status),
    priority: item.priority,
    priorityLabel: PRIORITY_LABELS[item.priority],
    progress: buildProgress(item, startDate, endDate),
    startDate,
    endDate,
    durationDays: item.duration_days,
    assigneeUserId: item.assignee?.id ?? null,
    updatedAt: item.updated_at,
  };
}

function toChartWorkItemDependency(
  dependency: ProjectWorkItemDependency,
): ChartWorkItemDependency {
  return {
    id: String(dependency.id),
    numericId: dependency.id,
    predecessorWorkItemId: String(dependency.predecessor_work_item_id),
    successorWorkItemId: String(dependency.successor_work_item_id),
  };
}

function toDhtmlxTask(item: ChartWorkItem): DhtmlxTask {
  const statusMeta = STATUS_META[item.status];

  return {
    id: item.id,
    parent: 0,
    text: item.title,
    description: item.description,
    start_date: parseLocalDate(item.startDate),
    end_date: addDays(parseLocalDate(item.endDate), 1),
    duration: Math.max(item.durationDays, 1),
    progress: item.progress / 100,
    code: item.code,
    owner: item.owner,
    assignee_user_id: item.assigneeUserId ? String(item.assigneeUserId) : "",
    status_code: item.status,
    status_label: statusMeta.label,
    priority_code: item.priority,
    priority_label: item.priorityLabel,
    creator_name: item.creatorName,
    start_label: formatDateLabel(item.startDate),
    end_label: formatDateLabel(item.endDate),
    updated_label: formatDateTimeLabel(item.updatedAt),
    color: statusMeta.barColor,
    progressColor: statusMeta.progressColor,
    textColor: "#ffffff",
    open: true,
  };
}

function toDhtmlxLink(dependency: ChartWorkItemDependency): Link {
  return {
    id: dependency.id,
    source: dependency.predecessorWorkItemId,
    target: dependency.successorWorkItemId,
    type: "0",
  };
}

function toApiStatus(status: WorkItemStatus): ProjectWorkItemSummary["status"] {
  if (status === "done") {
    return "DONE";
  }
  if (status === "in_progress") {
    return "IN_PROGRESS";
  }
  return "TODO";
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildQuickInfoContent(
  item: ChartWorkItem | undefined,
): string {
  if (!item) {
    return '<div class="gantt-quick-info-body"><p>워크아이템 정보를 불러오지 못했습니다.</p></div>';
  }

  return `
    <div class="gantt-quick-info-body">
      <p>${escapeHtml(item.description)}</p>
      <dl class="gantt-quick-info-grid">
        <div><dt>기간</dt><dd>${escapeHtml(formatDateLabel(item.startDate))} ~ ${escapeHtml(formatDateLabel(item.endDate))}</dd></div>
        <div><dt>담당자</dt><dd>${escapeHtml(item.owner)}</dd></div>
      </dl>
    </div>
  `;
}

export function ProjectGanttChart({
  projectId,
  startDate,
  endDate,
  projectMembers,
  isVisible,
}: ProjectGanttChartProps) {
  const shellRef = useRef<HTMLElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const ganttRef = useRef<GanttStatic | null>(null);
  const markerIdRef = useRef<string | number | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const snapshotRequestIdRef = useRef(0);
  const projectIdRef = useRef(projectId);
  const workItemsRef = useRef<ChartWorkItem[]>([]);
  const workItemMapRef = useRef<Map<string, ChartWorkItem>>(new Map());
  const dependenciesRef = useRef<ChartWorkItemDependency[]>([]);
  const projectMembersRef = useRef(projectMembers);
  const isApplyingSnapshotRef = useRef(false);
  const shouldCenterTodayRef = useRef(true);
  const hasBootstrappedRef = useRef(false);
  const [workItems, setWorkItems] = useState<ChartWorkItem[]>([]);
  const [dependencies, setDependencies] = useState<ChartWorkItemDependency[]>([]);
  const [selectedWorkItemId, setSelectedWorkItemId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isLinkSyncing, setIsLinkSyncing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<ProjectWorkItemSummary | null>(null);
  const [isDocumentVisible, setIsDocumentVisible] = useState(
    () => document.visibilityState === "visible",
  );
  const [currentZoomLevel, setCurrentZoomLevel] = useState<string>(ZOOM_LEVELS[1].name);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [socketStatus, setSocketStatus] = useState<"idle" | "connecting" | "live" | "offline">(
    "idle",
  );
  const [socketRetryKey, setSocketRetryKey] = useState(0);

  const today = useMemo(() => startOfDay(new Date()), []);
  const projectStart = useMemo(() => parseLocalDate(startDate), [startDate]);
  const projectEnd = useMemo(() => parseLocalDate(endDate), [endDate]);
  const chartRange = useMemo(() => {
    let rangeStart = projectStart;
    let rangeEnd = projectEnd;

    for (const item of workItems) {
      const itemStart = parseLocalDate(item.startDate);
      const itemEnd = parseLocalDate(item.endDate);
      if (itemStart.getTime() < rangeStart.getTime()) {
        rangeStart = itemStart;
      }
      if (itemEnd.getTime() > rangeEnd.getTime()) {
        rangeEnd = itemEnd;
      }
    }

    if (today.getTime() < rangeStart.getTime()) {
      rangeStart = today;
    }
    if (today.getTime() > rangeEnd.getTime()) {
      rangeEnd = today;
    }

    return {
      start: startOfMonth(rangeStart),
      end: endOfMonth(rangeEnd),
    };
  }, [projectEnd, projectStart, today, workItems]);

  projectIdRef.current = projectId;
  workItemsRef.current = workItems;
  workItemMapRef.current = new Map(workItems.map((item) => [item.id, item]));
  dependenciesRef.current = dependencies;
  projectMembersRef.current = projectMembers;

  useEffect(() => {
    shouldCenterTodayRef.current = true;
    hasBootstrappedRef.current = false;
    setSelectedWorkItemId(null);
    setWorkItems([]);
    setDependencies([]);
    setSocketRetryKey(0);
    setIsLoading(true);
    setLastSyncedAt(null);
    setErrorMessage(null);
  }, [projectId]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsDocumentVisible(document.visibilityState === "visible");
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

  async function refreshSnapshot(options?: { background?: boolean }) {
    const requestId = snapshotRequestIdRef.current + 1;
    snapshotRequestIdRef.current = requestId;

    if (options?.background) {
      setIsSyncing(true);
    } else {
      setIsLoading(true);
    }

    try {
      const response = await fetchProjectWorkItems(projectIdRef.current);
      if (snapshotRequestIdRef.current !== requestId) {
        return;
      }

      setWorkItems(response.items.map(toChartWorkItem));
      setDependencies(response.dependencies.map(toChartWorkItemDependency));
      setLastSyncedAt(new Date().toISOString());
      setErrorMessage(null);
      hasBootstrappedRef.current = true;
    } catch (error) {
      if (snapshotRequestIdRef.current !== requestId) {
        return;
      }

      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : "워크아이템 스냅샷을 불러오지 못했습니다.",
      );
    } finally {
      if (snapshotRequestIdRef.current === requestId) {
        setIsLoading(false);
        setIsSyncing(false);
      }
    }
  }

  async function persistLightboxWorkItem(taskId: string, task: DhtmlxTask) {
    const isNew = !workItemMapRef.current.get(taskId) || (task as any).$new;

    const title = task.text ? task.text.trim() : "";
    if (!title) {
      setErrorMessage("워크아이템 제목은 비워둘 수 없습니다.");
      return;
    }

    const scheduleStart = (task as any).schedule?.start_date;
    const scheduleEnd = (task as any).schedule?.end_date;

    try {
      if (isNew) {
        const payload: CreateProjectWorkItemPayload = {
          title,
          description: task.description ? task.description.trim() : "",
          status: toApiStatus(task.status_code || "TODO"),
          priority: task.priority_code || "MEDIUM",
          assignee_user_id: task.assignee_user_id ? Number(task.assignee_user_id) : null,
          timeline_start_date: toLocalIsoDate(startOfDay(scheduleStart ?? task.start_date ?? new Date())),
          timeline_end_date: toLocalIsoDate(
            addDays(startOfDay(scheduleEnd ?? task.end_date ?? addDays(new Date(), 1)), -1)
          ),
        };

        const response = await createProjectWorkItem(projectIdRef.current, payload);
        
        if (ganttRef.current?.isTaskExists(taskId)) {
          ganttRef.current.deleteTask(taskId);
        }

        const nextItem = toChartWorkItem(response.item);
        setWorkItems((current) => [...current, nextItem]);
        setSelectedWorkItemId(nextItem.id);
        setLastSyncedAt(new Date().toISOString());
        setErrorMessage(null);
        ganttRef.current?.hideLightbox();
        ganttRef.current?.showQuickInfo(nextItem.id);
      } else {
        const currentItem = workItemMapRef.current.get(taskId)!;
        const payload: UpdateProjectWorkItemPayload = {
          title,
          description: task.description ? task.description.trim() : "",
          status: toApiStatus(task.status_code),
          priority: task.priority_code,
          assignee_user_id: task.assignee_user_id ? Number(task.assignee_user_id) : null,
          timeline_start_date: toLocalIsoDate(startOfDay(scheduleStart ?? task.start_date ?? parseLocalDate(currentItem.startDate))),
          timeline_end_date: toLocalIsoDate(
            addDays(startOfDay(scheduleEnd ?? task.end_date ?? addDays(parseLocalDate(currentItem.endDate), 1)), -1)
          ),
        };

        const response = await updateProjectWorkItem(projectIdRef.current, currentItem.numericId, payload);
        const nextItem = toChartWorkItem(response.item);
        setWorkItems((current) => current.map((item) => (item.id === nextItem.id ? nextItem : item)));
        setSelectedWorkItemId(nextItem.id);
        setLastSyncedAt(new Date().toISOString());
        setErrorMessage(null);
        ganttRef.current?.hideLightbox();
        ganttRef.current?.showQuickInfo(nextItem.id);
      }
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "워크아이템을 저장하지 못했습니다.");
      void refreshSnapshot({ background: true });
    }
  }

  async function deleteWorkItemById(workItemId: string) {
    const currentItem = workItemMapRef.current.get(workItemId);
    if (!currentItem) {
      return;
    }

    const shouldDelete = window.confirm(
      `"${currentItem.title}" 워크아이템을 삭제하시겠습니까? 연결선만 정리하고 다른 워크아이템은 유지합니다.`,
    );
    if (!shouldDelete) {
      return;
    }

    try {
      await deleteProjectWorkItem(projectIdRef.current, currentItem.numericId);
      setWorkItems((current) => current.filter((item) => item.id !== currentItem.id));
      setDependencies((current) =>
        current.filter(
          (dependency) =>
            dependency.predecessorWorkItemId !== currentItem.id &&
            dependency.successorWorkItemId !== currentItem.id,
        ),
      );
      setSelectedWorkItemId(null);
      setLastSyncedAt(new Date().toISOString());
      setErrorMessage(null);
      ganttRef.current?.hideQuickInfo();
      ganttRef.current?.hideLightbox();
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : "워크아이템을 삭제하지 못했습니다.",
      );
      void refreshSnapshot({ background: true });
    }
  }

  useEffect(() => {
    let isDisposed = false;

    if (!isVisible || !isDocumentVisible) {
      return () => {
        isDisposed = true;
      };
    }

    void refreshSnapshot({ background: hasBootstrappedRef.current });

    const socket = new WebSocket(getProjectWorkItemsWebSocketUrl(projectId));
    socketRef.current = socket;
    setSocketStatus("connecting");

    socket.onopen = () => {
      if (!isDisposed) {
        setSocketStatus("live");
      }
    };

    socket.onmessage = (event) => {
      if (isDisposed) {
        return;
      }

      try {
        const payload = JSON.parse(event.data) as { type?: string };
        if (payload.type === "work_items_changed" || payload.type === "work_items_connected") {
          void refreshSnapshot({ background: true });
        }
      } catch {
        void refreshSnapshot({ background: true });
      }
    };

    socket.onerror = () => {
      if (!isDisposed) {
        setSocketStatus("offline");
      }
    };

    socket.onclose = () => {
      if (isDisposed) {
        return;
      }
      setSocketStatus("offline");
      reconnectTimerRef.current = window.setTimeout(() => {
        setSocketRetryKey((value) => value + 1);
      }, 1500);
    };

    return () => {
      isDisposed = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      socket.close();
      socketRef.current = null;
    };
  }, [isDocumentVisible, isVisible, projectId, socketRetryKey]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === shellRef.current);
      if (!ganttRef.current) {
        return;
      }

      shouldCenterTodayRef.current = true;
      window.requestAnimationFrame(() => {
        if (!ganttRef.current) {
          return;
        }
        ganttRef.current.setSizes();
        centerTimelineOnDate(ganttRef.current, today);
      });
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, [today]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return undefined;
    }

    const ganttInstance = gantt;
    const ganttConfig = ganttInstance.config as typeof ganttInstance.config & {
      quickinfo_buttons: string[];
      lightbox: {
        sections: Array<Record<string, unknown>>;
      };
    };
    const ganttWithButtons = ganttInstance as GanttStatic & {
      $click: {
        buttons: Record<string, (e: any, id?: any) => boolean | void>;
      };
    };
    ganttRef.current = ganttInstance;
    ganttInstance.plugins({ marker: true, fullscreen: true, quick_info: true });
    ganttInstance.clearAll();
    ganttInstance.config.readonly = false;
    ganttInstance.config.root_id = 0;
    ganttInstance.config.open_tree_initially = true;
    ganttInstance.config.show_progress = false;
    ganttInstance.config.drag_move = false;
    ganttInstance.config.drag_resize = false;
    ganttInstance.config.drag_progress = false;
    ganttInstance.config.drag_links = true;
    ganttInstance.config.details_on_dblclick = false;
    ganttInstance.config.show_quick_info = true;
    ganttInstance.config.initial_scroll = false;
    ganttInstance.config.wide_form = true;
    ganttInstance.config.grid_width = 356;
    ganttInstance.config.row_height = 56;
    ganttInstance.config.bar_height = 28;
    ganttInstance.config.show_links = true;
    ganttInstance.config.smart_scales = true;
    ganttConfig.quickinfo_buttons = ["icon_edit", "icon_delete"];
    ganttInstance.locale.labels.icon_edit = "수정";
    ganttInstance.locale.labels.icon_delete = "삭제";
    ganttInstance.locale.labels.section_title = "제목";
    ganttInstance.locale.labels.section_description = "설명";
    ganttInstance.locale.labels.section_status = "상태";
    ganttInstance.locale.labels.section_priority = "우선순위";
    ganttInstance.locale.labels.section_assignee = "담당자";
    ganttInstance.locale.labels.section_schedule = "기간";
    ganttInstance.form_blocks.date_range = {
      render() {
        return `<div class="gantt-date-range-editor">
          <label class="gantt-date-range-field">
            <span>시작일</span>
            <input type="date" class="gantt-date-range-input" name="start-date" />
          </label>
          <label class="gantt-date-range-field">
            <span>종료일</span>
            <input type="date" class="gantt-date-range-input" name="end-date" />
          </label>
        </div>`;
      },
      set_value(node, _value, task) {
        const startInput = node.querySelector<HTMLInputElement>('input[name="start-date"]');
        const endInput = node.querySelector<HTMLInputElement>('input[name="end-date"]');
        if (!startInput || !endInput) {
          return;
        }

        const start = startOfDay(task.start_date ?? today);
        const endExclusive = startOfDay(task.end_date ?? addDays(start, 1));
        const endInclusive = endExclusive.getTime() <= start.getTime() ? start : addDays(endExclusive, -1);
        const syncBounds = () => {
          endInput.min = startInput.value;
          if (endInput.value && endInput.value < startInput.value) {
            endInput.value = startInput.value;
          }
        };

        startInput.value = toLocalIsoDate(start);
        endInput.value = toLocalIsoDate(endInclusive);
        startInput.oninput = syncBounds;
        syncBounds();
      },
      get_value(node, _task) {
        const startInput = node.querySelector<HTMLInputElement>('input[name="start-date"]');
        const endInput = node.querySelector<HTMLInputElement>('input[name="end-date"]');
        const fallbackStart = startOfDay(today);
        const start = startInput?.value ? parseLocalDate(startInput.value) : fallbackStart;
        const end = endInput?.value ? parseLocalDate(endInput.value) : start;
        return {
          start_date: start,
          end_date: addDays(end.getTime() < start.getTime() ? start : end, 1),
        };
      },
      focus(node) {
        node.querySelector<HTMLInputElement>('input[name="start-date"]')?.focus();
      },
    };
    ganttConfig.lightbox.sections = [
      { name: "title", height: 42, map_to: "text", type: "textarea", focus: true },
      { name: "description", height: 86, map_to: "description", type: "textarea" },
      {
        name: "status",
        height: 42,
        map_to: "status_code",
        type: "select",
        options: [
          { key: "planned", label: STATUS_META.planned.label },
          { key: "in_progress", label: STATUS_META.in_progress.label },
          { key: "done", label: STATUS_META.done.label },
        ],
      },
      {
        name: "priority",
        height: 42,
        map_to: "priority_code",
        type: "select",
        options: [
          { key: "LOW", label: PRIORITY_LABELS.LOW },
          { key: "MEDIUM", label: PRIORITY_LABELS.MEDIUM },
          { key: "HIGH", label: PRIORITY_LABELS.HIGH },
        ],
      },
      {
        name: "assignee",
        height: 42,
        map_to: "assignee_user_id",
        type: "select",
        options: [
          { key: "", label: "미정" },
          ...projectMembersRef.current.map((member) => ({
            key: String(member.user_id),
            label: `${member.name} · ${member.position_label}`,
          })),
        ],
      },
      { name: "schedule", height: 78, map_to: "schedule", type: "date_range" },
    ];
    ganttInstance.config.columns = [
      { name: "text", label: "워크아이템", tree: true, width: 210, resize: true },
      { name: "owner", label: "담당자", align: "center", width: 82 },
      { name: "status_label", label: "상태", align: "center", width: 64 },
    ];
    ganttInstance.templates.scale_cell_class = (date) => (date.getDate() === 1 ? "gantt-month-boundary-cell" : "");
    ganttInstance.templates.timeline_cell_class = (_task, date) => {
      if (
        date.getFullYear() === today.getFullYear() &&
        date.getMonth() === today.getMonth() &&
        date.getDate() === today.getDate()
      ) {
        return "gantt-timeline-today-cell";
      }
      return "";
    };
    ganttInstance.templates.task_text = (_start, _end, task) => (task as DhtmlxTask).code;
    ganttInstance.templates.task_class = (_start, _end, task) => {
      const ganttTask = task as DhtmlxTask;
      return `gantt-task-status-${ganttTask.status_code}`;
    };
    ganttInstance.templates.link_class = () => "gantt-work-item-link";
    ganttInstance.templates.quick_info_title = (_start, _end, task) => {
      const ganttTask = task as DhtmlxTask;
      return `${ganttTask.code} · ${ganttTask.text}`;
    };
    ganttInstance.templates.quick_info_content = (_start, _end, task) =>
      buildQuickInfoContent(workItemMapRef.current.get(String(task.id)));
    ganttInstance.templates.quick_info_date = (_start, _end, task) => {
      const ganttTask = task as DhtmlxTask;
      return `${ganttTask.start_label} ~ ${ganttTask.end_label}`;
    };
    ganttInstance.ext.zoom.init({
      activeLevelIndex: 1,
      minColumnWidth: 34,
      maxColumnWidth: 64,
      levels: ZOOM_LEVELS.map((level) => ({
        name: level.name,
        min_column_width: level.min_column_width,
        scale_height: 54,
        scales: [
          { unit: "month", step: 1, format: formatMonthScale },
          { unit: "day", step: 1, format: "%d" },
        ],
      })),
    });
    ganttWithButtons.$click = ganttWithButtons.$click || {};
    ganttWithButtons.$click.buttons = ganttWithButtons.$click.buttons || {};
    ganttWithButtons.$click.buttons.edit = (e: any, id?: any) => {
      const taskId = id || (typeof e === "object" ? ganttInstance.locate(e) || ganttInstance.getSelectedId() : e);
      if (taskId != null) {
        const item = workItemMapRef.current.get(String(taskId));
        if (item) {
          setEditingTask({
            id: item.numericId,
            title: item.title,
            description: item.description === "설명이 아직 없습니다." ? "" : item.description,
            status: item.status === "done" ? "DONE" : item.status === "in_progress" ? "IN_PROGRESS" : "TODO",
            priority: item.priority,
            due_date: null,
            started_at: null,
            completed_at: null,
            created_at: "",
            updated_at: item.updatedAt,
            timeline_start_date: item.startDate,
            timeline_end_date: item.endDate,
            duration_days: item.durationDays,
            creator: { id: -1, name: item.creatorName },
            assignee: item.assigneeUserId ? { id: item.assigneeUserId, name: item.owner } : null,
          } as ProjectWorkItemSummary);
        }
      }
      return false;
    };
    ganttWithButtons.$click.buttons.delete = (e: any, id?: any) => {
      const taskId = id || (typeof e === "object" ? ganttInstance.locate(e) || ganttInstance.getSelectedId() : e);
      if (taskId != null) {
        void deleteWorkItemById(String(taskId));
      }
      return false;
    };
    ganttInstance.init(container);

    const taskData = ganttInstance.$task_data as HTMLElement | undefined;
    const handleTimelineWheel = (event: WheelEvent) => {
      if (!event.shiftKey) {
        return;
      }

      event.preventDefault();
      const { x, y } = ganttInstance.getScrollState();
      const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      ganttInstance.scrollTo(Math.max(x + delta, 0), y);
    };

    taskData?.addEventListener("wheel", handleTimelineWheel, { passive: false });

    const zoomEventId = ganttInstance.ext.zoom.attachEvent("onAfterZoom", (_level, config) => {
      setCurrentZoomLevel(config.name);
      shouldCenterTodayRef.current = true;
      window.requestAnimationFrame(() => {
        if (ganttRef.current) {
          centerTimelineOnDate(ganttRef.current, today);
        }
      });
      return true;
    });
    const taskClickEventId = ganttInstance.attachEvent("onTaskClick", (id) => {
      setSelectedWorkItemId(String(id));
      ganttInstance.selectTask(id);
      return true;
    });
    const emptyClickEventId = ganttInstance.attachEvent("onEmptyClick", () => {
      setSelectedWorkItemId(null);
      ganttInstance.hideQuickInfo();
      ganttInstance.unselectTask();
    });
    const beforeLinkAddEventId = ganttInstance.attachEvent("onBeforeLinkAdd", (_id, link) => {
      if (isApplyingSnapshotRef.current) {
        return true;
      }

      if (String(link.source) === String(link.target)) {
        setErrorMessage("같은 워크아이템끼리는 연결할 수 없습니다.");
        return false;
      }

      const isDuplicate = dependenciesRef.current.some(
        (dependency) =>
          dependency.predecessorWorkItemId === String(link.source) &&
          dependency.successorWorkItemId === String(link.target),
      );
      if (isDuplicate) {
        setErrorMessage("이미 연결된 워크아이템 관계입니다.");
        return false;
      }

      setErrorMessage(null);
      return true;
    });
    const afterLinkAddEventId = ganttInstance.attachEvent("onAfterLinkAdd", (id, link) => {
      if (isApplyingSnapshotRef.current) {
        return;
      }

      setIsLinkSyncing(true);
      void createProjectWorkItemDependency(projectIdRef.current, {
        predecessor_work_item_id: Number(link.source),
        successor_work_item_id: Number(link.target),
      })
        .then((response) => {
          isApplyingSnapshotRef.current = true;
          if (ganttInstance.isLinkExists(id)) {
            ganttInstance.changeLinkId(id, String(response.dependency.id));
          }
          isApplyingSnapshotRef.current = false;
          
          setDependencies((current) => {
            const nextDependency = toChartWorkItemDependency(response.dependency);
            const filtered = current.filter((dependency) => dependency.id !== String(id) && dependency.id !== String(response.dependency.id));
            return [...filtered, nextDependency];
          });
          setErrorMessage(null);
        })
        .catch((error: unknown) => {
          if (ganttInstance.isLinkExists(id)) {
            isApplyingSnapshotRef.current = true;
            ganttInstance.deleteLink(id);
            isApplyingSnapshotRef.current = false;
          }
          setErrorMessage(
            error instanceof ApiError ? error.message : "워크아이템 연결을 저장하지 못했습니다.",
          );
        })
        .finally(() => {
          setIsLinkSyncing(false);
        });
    });
    const afterLinkDeleteEventId = ganttInstance.attachEvent("onAfterLinkDelete", (id) => {
      if (isApplyingSnapshotRef.current) {
        return;
      }

      setIsLinkSyncing(true);
      void deleteProjectWorkItemDependency(projectIdRef.current, Number(id))
        .then(() => {
          setDependencies((current) =>
            current.filter((dependency) => dependency.id !== String(id)),
          );
          setErrorMessage(null);
        })
        .catch((error: unknown) => {
          setErrorMessage(
            error instanceof ApiError ? error.message : "워크아이템 연결을 삭제하지 못했습니다.",
          );
          void refreshSnapshot({ background: true });
        })
        .finally(() => {
          setIsLinkSyncing(false);
        });
    });
    const lightboxSaveEventId = ganttInstance.attachEvent("onLightboxSave", (id, task) => {
      void persistLightboxWorkItem(String(id), task as DhtmlxTask);
      return false;
    });
    const lightboxDeleteEventId = ganttInstance.attachEvent("onLightboxDelete", (id) => {
      void deleteWorkItemById(String(id));
      return false;
    });

    return () => {
      taskData?.removeEventListener("wheel", handleTimelineWheel);
      ganttInstance.ext.zoom.detachEvent(zoomEventId);
      ganttInstance.detachEvent(taskClickEventId);
      ganttInstance.detachEvent(emptyClickEventId);
      ganttInstance.detachEvent(beforeLinkAddEventId);
      ganttInstance.detachEvent(afterLinkAddEventId);
      ganttInstance.detachEvent(afterLinkDeleteEventId);
      ganttInstance.detachEvent(lightboxSaveEventId);
      ganttInstance.detachEvent(lightboxDeleteEventId);
      if (markerIdRef.current !== null) {
        ganttInstance.deleteMarker(markerIdRef.current);
        markerIdRef.current = null;
      }
      ganttInstance.clearAll();
      ganttRef.current = null;
    };
  }, [today]);

  useEffect(() => {
    const ganttInstance = ganttRef.current;
    if (!ganttInstance) {
      return;
    }

    const scrollState = ganttInstance.getScrollState();
    const nextTasks = workItems.map(toDhtmlxTask);
    const nextLinks = dependencies.map(toDhtmlxLink);
    const nextTaskIds = new Set(nextTasks.map((task) => String(task.id)));
    const nextLinkIds = new Set(nextLinks.map((link) => String(link.id)));
    const existingTaskIds: string[] = [];
    const existingLinkIds = ganttInstance.getLinks().map((link) => String(link.id));

    ganttInstance.eachTask((task) => {
      existingTaskIds.push(String(task.id));
    });

    isApplyingSnapshotRef.current = true;
    ganttInstance.batchUpdate(() => {
      ganttInstance.config.start_date = chartRange.start;
      ganttInstance.config.end_date = chartRange.end;
      for (const task of nextTasks) {
        if (ganttInstance.isTaskExists(task.id)) {
          Object.assign(ganttInstance.getTask(task.id), task);
          ganttInstance.updateTask(task.id);
        } else {
          ganttInstance.addTask(task, 0);
        }
      }
      for (const existingTaskId of existingTaskIds) {
        if (existingTaskId !== "0" && !nextTaskIds.has(existingTaskId) && ganttInstance.isTaskExists(existingTaskId)) {
          ganttInstance.deleteTask(existingTaskId);
        }
      }
      for (const link of nextLinks) {
        if (ganttInstance.isLinkExists(link.id)) {
          Object.assign(ganttInstance.getLink(link.id), link);
          ganttInstance.updateLink(link.id);
        } else {
          ganttInstance.addLink(link);
        }
      }
      for (const existingLinkId of existingLinkIds) {
        if (!nextLinkIds.has(existingLinkId) && ganttInstance.isLinkExists(existingLinkId)) {
          ganttInstance.deleteLink(existingLinkId);
        }
      }
      if (markerIdRef.current !== null) {
        ganttInstance.deleteMarker(markerIdRef.current);
        markerIdRef.current = null;
      }
      markerIdRef.current = ganttInstance.addMarker({
        start_date: today,
        css: "gantt-today-marker",
        // text: "오늘",
        title: formatDateLabel(toLocalIsoDate(today)),
      });
    });
    isApplyingSnapshotRef.current = false;

    window.requestAnimationFrame(() => {
      if (!ganttRef.current) {
        return;
      }
      ganttRef.current.setSizes();
      if (shouldCenterTodayRef.current || !isDateVisible(ganttRef.current, today)) {
        centerTimelineOnDate(ganttRef.current, today);
        shouldCenterTodayRef.current = false;
      } else {
        ganttRef.current.scrollTo(scrollState.x, scrollState.y);
      }
    });
  }, [chartRange.end, chartRange.start, dependencies, today, workItems]);

  useEffect(() => {
    const ganttInstance = ganttRef.current;
    if (!ganttInstance) {
      return;
    }
    if (selectedWorkItemId && ganttInstance.isTaskExists(selectedWorkItemId)) {
      ganttInstance.selectTask(selectedWorkItemId);
      return;
    }
    ganttInstance.unselectTask();
  }, [selectedWorkItemId]);

  useEffect(() => {
    if (!isVisible || !ganttRef.current) {
      return;
    }

    shouldCenterTodayRef.current = true;
    window.requestAnimationFrame(() => {
      if (!ganttRef.current) {
        return;
      }
      ganttRef.current.setSizes();
      if (!isDateVisible(ganttRef.current, today)) {
        centerTimelineOnDate(ganttRef.current, today);
      }
      shouldCenterTodayRef.current = false;
    });
  }, [isVisible, today]);

  const handleZoomIn = () => {
    ganttRef.current?.ext.zoom.zoomIn();
  };

  const handleZoomOut = () => {
    ganttRef.current?.ext.zoom.zoomOut();
  };

  const handleFocusToday = () => {
    if (!ganttRef.current) {
      return;
    }
    shouldCenterTodayRef.current = false;
    centerTimelineOnDate(ganttRef.current, today);
  };

  const handleToggleFullscreen = async () => {
    const shell = shellRef.current;
    if (!shell) {
      return;
    }
    if (document.fullscreenElement === shell) {
      await document.exitFullscreen();
      return;
    }
    await shell.requestFullscreen();
  };

  /*
  const handleSaveSelectedWorkItem = async () => {
    if (!selectedWorkItem || !inspectorDraft) {
      return;
    }

    const title = inspectorDraft.title.trim();
    if (!title) {
      setErrorMessage("워크아이템 제목은 비워둘 수 없습니다.");
      return;
    }

    const payload: UpdateProjectWorkItemPayload = {
      title,
      description: inspectorDraft.description.trim(),
      status: inspectorDraft.status,
      priority: inspectorDraft.priority,
      assignee_user_id: inspectorDraft.assigneeUserId ? Number(inspectorDraft.assigneeUserId) : null,
      timeline_start_date: inspectorDraft.timelineStartDate,
      timeline_end_date: inspectorDraft.timelineEndDate,
    };

    setIsSaving(true);
    try {
      const response = await updateProjectWorkItem(projectId, selectedWorkItem.numericId, payload);
      const nextItem = toChartWorkItem(response.item);
      setWorkItems((current) => current.map((item) => (item.id === nextItem.id ? nextItem : item)));
      setSelectedWorkItemId(nextItem.id);
      setInspectorDraft(buildInspectorFormState(nextItem));
      setIsEditing(false);
      setLastSyncedAt(new Date().toISOString());
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : "워크아이템을 수정하지 못했습니다.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteSelectedWorkItem = async () => {
    if (!selectedWorkItem) {
      return;
    }

    const shouldDelete = window.confirm(
      `"${selectedWorkItem.title}" 워크아이템을 삭제하시겠습니까? 연결선만 정리되고 다른 워크아이템은 유지됩니다.`,
    );
    if (!shouldDelete) {
      return;
    }

    setIsDeleting(true);
    try {
      await deleteProjectWorkItem(projectId, selectedWorkItem.numericId);
      setWorkItems((current) => current.filter((item) => item.id !== selectedWorkItem.id));
      setDependencies((current) =>
        current.filter(
          (dependency) =>
            dependency.predecessorWorkItemId !== selectedWorkItem.id &&
            dependency.successorWorkItemId !== selectedWorkItem.id,
        ),
      );
      setSelectedWorkItemId(null);
      setInspectorDraft(null);
      setIsEditing(false);
      setLastSyncedAt(new Date().toISOString());
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : "워크아이템을 삭제하지 못했습니다.",
      );
    } finally {
      setIsDeleting(false);
    }
  };
  */

  return (
    <section ref={shellRef} className="gantt-card">
      <div className="section-heading">
        <div>
          {/* <p className="section-label">gantt</p> */}
          <h2>프로젝트 일정</h2>
        </div>
      </div>

      <div className="gantt-toolbar">
        <div className="gantt-toolbar-copy">
          {/* <p className={`gantt-sync-note ${errorMessage ? "gantt-sync-note-error" : ""}`}>
            {errorMessage
              ? errorMessage
              : socketStatus === "live"
                ? "REST 스냅샷 + WebSocket으로 실시간 반영합니다."
                : isVisible && isDocumentVisible
                  ? "초기 스냅샷을 동기화하고 실시간 연결을 준비 중입니다."
                  : "개요 화면을 보고 있을 때만 실시간 동기화합니다."}
          </p> */}

          <div className="gantt-toolbar-actions-row">
            {/* <div className="gantt-zoom-controls">
              <button type="button" className="gantt-zoom-button" onClick={handleZoomOut}>
                -
              </button>
              <div className="gantt-zoom-level">
                <strong>{currentZoomLevel}</strong>
                <span>Shift + wheel 좌우 스크롤</span>
              </div>
              <button type="button" className="gantt-zoom-button" onClick={handleZoomIn}>
                +
              </button>
            </div> */}

            <div className="gantt-toolbar-actions-row">
              <button
                type="button"
                className="gantt-fullscreen-button"
                // style={{ backgroundColor: "var(--color-primary-600)", color: "#a13d3d", border: "none" }}
                onClick={() => setIsCreateOpen(true)}
              >
                + 할일 등록
              </button>
              <button type="button" className="gantt-fullscreen-button" onClick={handleFocusToday}>
                오늘로 이동
              </button>
              <button
                type="button"
                className="gantt-fullscreen-button"
                onClick={() => void handleToggleFullscreen()}
              >
                {isFullscreen ? "전체화면 종료" : "전체화면"}
              </button>
            </div>
          </div>

          {/* {lastSyncedAt ? (
            <span className="gantt-sync-meta">
              마지막 동기화 {formatDateTimeLabel(lastSyncedAt)} · 워크아이템 {workItems.length}건 ·
              연결 {dependencies.length}건
              {isLinkSyncing ? " · 연결 저장 중" : ""}
              {isSyncing ? " · 갱신 중" : ""}
            </span>
          ) : null} */}
        </div>

        <div className="gantt-legend-group">
          {Object.entries(STATUS_META).map(([status, meta]) => (
            <div key={status} className="gantt-legend-item">
              <span
                className="gantt-legend-dot"
                style={{ backgroundColor: meta.barColor }}
                aria-hidden="true"
              />
              <span>{meta.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="gantt-workspace-layout">
        <div className="gantt-library-shell">
          <div ref={containerRef} className="gantt-library-host" />
          {!isLoading && !errorMessage && workItems.length === 0 ? (
            <div className="gantt-empty-state">
              <strong>아직 표시할 워크아이템이 없습니다.</strong>
              <span>워크아이템이 추가되면 이 영역에 막대와 연결선이 함께 그려집니다.</span>
            </div>
          ) : null}
        </div>
      </div>
      <ProjectTaskCreateOverlay
        open={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        projectId={projectId}
        initialStatus="TODO"
        onCreated={() => {
          setIsCreateOpen(false);
          // Snapshot polling isn't triggered manually, but maybe we can wait
          // or we just rely on the WebSocket or the next polling cycle.
          // Since the server sends socket messages, it will update automatically.
        }}
      />
      <ProjectTaskEditOverlay
        open={editingTask !== null}
        onClose={() => setEditingTask(null)}
        projectId={projectId}
        task={editingTask}
        onUpdated={() => {
          setEditingTask(null);
        }}
      />
    </section>
  );
}
