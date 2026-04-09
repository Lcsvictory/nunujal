import React, { useState, useEffect } from "react";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragOverEvent,
  DragEndEvent,
  defaultDropAnimationSideEffects,
  useDroppable,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { fetchProjectWorkItems, updateProjectWorkItem, deleteProjectWorkItem } from "./api";
import type { ProjectDetail, ProjectWorkItemSummary } from "./types";
import { ProjectTaskCreateOverlay } from "./ProjectTaskCreateOverlay";
import { ProjectTaskEditOverlay } from "./ProjectTaskEditOverlay";
import "./ProjectTasksPage.css";

type ProjectTasksPageProps = {
  project: ProjectDetail;
};

const STATUSES = ["TODO", "IN_PROGRESS", "DONE"] as const;
type TaskStatus = typeof STATUSES[number];

const STATUS_LABELS: Record<TaskStatus, string> = {
  TODO: "진행 예정",
  IN_PROGRESS: "진행 중",
  DONE: "완료",
};

export const ProjectTasksPage: React.FC<ProjectTasksPageProps> = ({ project }) => {
  const [items, setItems] = useState<Record<TaskStatus, ProjectWorkItemSummary[]>>({
    TODO: [],
    IN_PROGRESS: [],
    DONE: [],
  });
  const [activeId, setActiveId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [createStatus, setCreateStatus] = useState<TaskStatus | null>(null);
  const [editingTask, setEditingTask] = useState<ProjectWorkItemSummary | null>(null);
  const [pendingDoneTask, setPendingDoneTask] = useState<{
    task: ProjectWorkItemSummary;
    originalStatus: TaskStatus;
  } | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    task: ProjectWorkItemSummary;
  } | null>(null);

  // Filters
  const [filterAssignee, setFilterAssignee] = useState<number | "ALL">("ALL");
  const [filterPriority, setFilterPriority] = useState<string>("ALL");
  const [filterSearch, setFilterSearch] = useState("");

  useEffect(() => {
    const handleGlobalClick = () => setContextMenu(null);
    window.addEventListener("click", handleGlobalClick);
    window.addEventListener("scroll", handleGlobalClick);
    return () => {
      window.removeEventListener("click", handleGlobalClick);
      window.removeEventListener("scroll", handleGlobalClick);
    };
  }, []);

  useEffect(() => {
    loadItems();
  }, [project.id]);

  const loadItems = async () => {
    try {
      setLoading(true);
      const res = await fetchProjectWorkItems(project.id);
      const newItems: Record<TaskStatus, ProjectWorkItemSummary[]> = {
        TODO: [],
        IN_PROGRESS: [],
        DONE: [],
      };
      
      // Sort tasks by something if needed. Here we just group them.
      res.items.forEach((item) => {
        if (STATUSES.includes(item.status as TaskStatus)) {
          newItems[item.status as TaskStatus].push(item);
        }
      });
      setItems(newItems);
    } catch (e) {
      console.error("Failed to load tasks", e);
    } finally {
      setLoading(false);
    }
  };

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5, // 5px drag threshold
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const findContainer = (id: number): TaskStatus | undefined => {
    if ((STATUSES as readonly string[]).includes(String(id))) return id as unknown as TaskStatus;
    for (const key of STATUSES) {
      if (items[key as TaskStatus].find((item) => item.id === id)) {
        return key as TaskStatus;
      }
    }
    return undefined;
  };

  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    setActiveId(active.id as number);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    const overId = over?.id;

    if (!overId || active.id === overId) {
      return;
    }

    const activeContainer = findContainer(active.id as number);
    const overContainer = findContainer(overId as number);

    // 완료된 태스크는 다른 상태로 이동 불가
    if (activeContainer === "DONE" && overContainer !== "DONE") {
      return;
    }

    if (!activeContainer || !overContainer || activeContainer === overContainer) {
      return;
    }

    setItems((prev) => {
      const activeItems = prev[activeContainer];
      const overItems = prev[overContainer];
      const activeIndex = activeItems.findIndex((i) => i.id === active.id);
      const overIndex =
        overId in prev
          ? overItems.length + 1
          : overItems.findIndex((i) => i.id === overId);

      let newIndex;
      if (overId in prev) {
        newIndex = overItems.length + 1;
      } else {
        const isBelowOverItem =
          over &&
          active.rect.current.translated &&
          active.rect.current.translated.top > over.rect.top + over.rect.height;
        const modifier = isBelowOverItem ? 1 : 0;
        newIndex = overIndex >= 0 ? overIndex + modifier : overItems.length + 1;
      }

      return {
        ...prev,
        [activeContainer]: activeItems.filter((i) => i.id !== active.id),
        [overContainer]: [
          ...overItems.slice(0, newIndex),
          activeItems[activeIndex],
          ...overItems.slice(newIndex, overItems.length),
        ],
      };
    });
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    const activeContainer = findContainer(active.id as number);
    const overContainer = findContainer(over?.id as number);

    // 완료된 태스크는 다른 상태로 이동 불가 (DragOver에서 막았지만 이중 체크)
    if (activeContainer === "DONE" && overContainer !== "DONE") {
      setActiveId(null);
      return;
    }

    if (
      !activeContainer ||
      !overContainer ||
      activeContainer !== overContainer
    ) {
      setActiveId(null);
      return;
    }

    const activeIndex = items[activeContainer].findIndex((i) => i.id === active.id);
    const overIndex = items[overContainer].findIndex((i) => i.id === over?.id);

    // If dragged to a different position in the same list
    if (activeIndex !== overIndex) {
      setItems((prev) => ({
        ...prev,
        [overContainer]: arrayMove(prev[overContainer], activeIndex, overIndex),
      }));
    }

    setActiveId(null);

    // After state update, check if status changed.
    // Dnd-kit's handleDragOver eagerly moves the item between arrays.
    // Now we must trigger the API call if it actually landed in a new status.
    const itemToUpdate = items[overContainer].find(i => i.id === active.id) || items[activeContainer]?.find(i=>i.id === active.id);
    
    // Oh wait, in DragEnd, the container migration already happened in DragOver. 
    // To know if status changed, we just look at what array it is in now compared to its real item.status
    if (itemToUpdate && itemToUpdate.status !== overContainer) {
      if (overContainer === "DONE") {
        // Show evidence modal before completing
        setPendingDoneTask({ task: itemToUpdate, originalStatus: itemToUpdate.status as TaskStatus });
      } else {
        // Optimistic update already ran!
        try {
          await updateProjectWorkItem(project.id, itemToUpdate.id, {
            status: overContainer
          });
          itemToUpdate.status = overContainer; // update local ref
        } catch (err) {
          console.error("Failed to update status", err);
          // Better error handling: revert changes by reloading
          loadItems();
        }
      }
    }
  };

  const handleCreateTask = async () => {
    setCreateStatus(null);
    await loadItems();
  };

  const handleEditTask = async () => {
    setEditingTask(null);
    await loadItems();
  };

  const handleDeleteTask = async (taskId: number) => {
    if (!window.confirm("정말로 이 할일을 삭제하시겠습니까?")) return;
    try {
      await deleteProjectWorkItem(project.id, taskId);
      await loadItems();
    } catch (error) {
      console.error("삭제 실패", error);
      alert("할일을 삭제하지 못했습니다.");
    }
  }

  const handleContextMenu = (e: React.MouseEvent, task: ProjectWorkItemSummary) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      task,
    });
  };

  const renderSortableItem = (item: ProjectWorkItemSummary) => {
    return (
      <SortableTaskCard key={item.id} item={item} onContextMenu={handleContextMenu} />
    );
  };

  const activeItem = activeId 
    ? [...items.TODO, ...items.IN_PROGRESS, ...items.DONE].find(i => i.id === activeId) 
    : null;

  const getFilteredItems = (status: TaskStatus) => {
    return items[status].filter((item) => {
      if (filterAssignee !== "ALL" && item.assignee?.id !== filterAssignee) return false;
      if (filterPriority !== "ALL" && item.priority !== filterPriority) return false;
      if (filterSearch && !item.title.toLowerCase().includes(filterSearch.toLowerCase())) return false;
      return true;
    });
  };

  const handleDoneCancel = () => {
    setPendingDoneTask(null);
    loadItems(); // Revert optimism
  };

  const handleDoneSubmit = async (evidenceUrl: string) => {
    if (!pendingDoneTask) return;
    try {
      // NOTE: Here we append evidenceUrl or send it to the specialized endpoint.
      // E.g., appending link to description so AI can find it later.
      const newDesc = pendingDoneTask.task.description
        ? `${pendingDoneTask.task.description}\n\n[Evidence]: ${evidenceUrl}`
        : `[Evidence]: ${evidenceUrl}`;

      await updateProjectWorkItem(project.id, pendingDoneTask.task.id, {
        status: "DONE",
        description: newDesc,
      });
      await loadItems();
    } catch (err) {
      console.error("Failed to complete task", err);
      alert("할일을 완료 처리하는데 실패했습니다.");
      loadItems();
    } finally {
      setPendingDoneTask(null);
    }
  };

  if (loading) return <div className="p-tasks-loading">불러오는 중...</div>;

  return (
    <div className="p-tasks-board-container">
      <div className="p-tasks-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>할일 보드</h2>
        <button
          className="button button-primary"
          onClick={() => setCreateStatus("TODO")}
          style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: '#0066ff', color: 'white', cursor: 'pointer' }}
        >
          + 할일 추가
        </button>
      </div>

      <div className="p-tasks-filters" style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
        <input
          type="text"
          placeholder="할일 검색..."
          value={filterSearch}
          onChange={(e) => setFilterSearch(e.target.value)}
          style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
        />
        <select
          value={filterAssignee}
          onChange={(e) => setFilterAssignee(e.target.value === "ALL" ? "ALL" : Number(e.target.value))}
          style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
        >
          <option value="ALL">모든 작업자</option>
          {project.members?.map(m => (
            <option key={m.user_id} value={m.user_id}>{m.name}</option>
          ))}
        </select>
        <select
          value={filterPriority}
          onChange={(e) => setFilterPriority(e.target.value)}
          style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
        >
          <option value="ALL">모든 우선순위</option>
          <option value="HIGH">높음 ↑</option>
          <option value="MEDIUM">중간 ＝</option>
          <option value="LOW">낮음 ↓</option>
        </select>
      </div>

      <div className="p-tasks-board">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          {STATUSES.map((status) => (
            <KanbanColumn
              key={status}
              id={status}
              title={STATUS_LABELS[status]}
              items={getFilteredItems(status)}
              onContextMenu={handleContextMenu}
            />
          ))}
          <DragOverlay
            dropAnimation={{
              sideEffects: defaultDropAnimationSideEffects({
                styles: { active: { opacity: "0.5" } }
              })
            }}
          >
            {activeItem ? <TaskCard item={activeItem} isDragging /> : null}
          </DragOverlay>
        </DndContext>
      </div>

      {contextMenu && (
        <div
          className="p-tasks-context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => {
              setEditingTask(contextMenu.task);
              setContextMenu(null);
            }}
          >
            수정
          </button>
          <button
            className="danger"
            onClick={() => {
              handleDeleteTask(contextMenu.task.id);
              setContextMenu(null);
            }}
          >
            삭제
          </button>
        </div>
      )}

      <ProjectTaskCreateOverlay
        open={createStatus !== null}
        onClose={() => setCreateStatus(null)}
        projectId={project.id}
        initialStatus={createStatus || "TODO"}
        onCreated={handleCreateTask}
      />

      <ProjectTaskEditOverlay
        open={editingTask !== null}
        onClose={() => setEditingTask(null)}
        projectId={project.id}
        task={editingTask}
        onUpdated={handleEditTask}
      />

      {pendingDoneTask && (
        <div className="p-tasks-context-menu" style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: "400px", padding: "24px", background: "white", borderRadius: "8px", boxShadow: "0 4px 12px rgba(0,0,0,0.15)", zIndex: 1000 }} onClick={e => e.stopPropagation()}>
          <h3 style={{ marginBottom: "16px" }}>작업 완료 증빙 제출</h3>
          <p style={{ fontSize: "14px", color: "#555", marginBottom: "16px" }}>
            작업 완료를 위해 증빙 자료(URL 링크 등)를 제출해주세요.<br/>
            (예: Google Docs 링크, Notion 페이지, Github PR 주소 등)
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <input
              id="evidence-input"
              type="text"
              placeholder="https://..."
              style={{ width: "100%", padding: "8px", border: "1px solid #ccc", borderRadius: "4px" }}
              autoFocus
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
              <button
                onClick={handleDoneCancel}
                style={{ padding: "8px 16px", background: "#f1f1f1", border: "none", borderRadius: "4px", cursor: "pointer" }}
              >
                취소
              </button>
              <button
                onClick={() => {
                  const input = document.getElementById("evidence-input") as HTMLInputElement;
                  if (!input.value.trim()) {
                    alert("증빙 URL을 입력해주세요.");
                    return;
                  }
                  handleDoneSubmit(input.value.trim());
                }}
                style={{ padding: "8px 16px", background: "#0066ff", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
              >
                완료 처리
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ====================== Column Component ======================
type KanbanColumnProps = {
  id: TaskStatus;
  title: string;
  items: ProjectWorkItemSummary[];
  onContextMenu: (e: React.MouseEvent, task: ProjectWorkItemSummary) => void;
};

function KanbanColumn({ id, title, items, onContextMenu }: KanbanColumnProps) {
  const { setNodeRef } = useDroppable({ id });

  return (
    <div className="p-tasks-column" ref={setNodeRef}>
      <div className="p-tasks-column-header">
        <h3 className="p-tasks-column-title">{title}</h3>
        <span className="p-tasks-column-count">{items.length}</span>
      </div>

      <div className="p-tasks-column-content">
        <SortableContext id={id} items={items} strategy={verticalListSortingStrategy}>
          <div className="p-tasks-sortable-list">
            {items.map((item) => (
              <SortableTaskCard key={item.id} item={item} onContextMenu={onContextMenu} />
            ))}
          </div>
        </SortableContext>
      </div>
    </div>
  );
}

// ====================== Task Card Component ======================
function SortableTaskCard({
  item,
  onContextMenu,
}: {
  item: ProjectWorkItemSummary;
  onContextMenu: (e: React.MouseEvent, task: ProjectWorkItemSummary) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id, disabled: item.status === "DONE" });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
    cursor: item.status === "DONE" ? "not-allowed" : "grab",
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...(item.status === "DONE" ? {} : listeners)}>      <TaskCard item={item} onContextMenu={onContextMenu} />
    </div>
  );
}

function TaskCard({
  item,
  isDragging,
  onContextMenu,
}: {
  item: ProjectWorkItemSummary;
  isDragging?: boolean;
  onContextMenu?: (e: React.MouseEvent, task: ProjectWorkItemSummary) => void;
}) {
  return (
    <div
      className={`p-task-card ${isDragging ? "is-dragging" : ""}`}
      onContextMenu={(e) => onContextMenu?.(e, item)}
    >
      <div className="p-task-card-title">{item.title}</div>
      <div className="p-task-card-footer">
        <div className="p-task-priority">
          {item.priority === "HIGH" && <span className="p-prio high">↑</span>}
          {item.priority === "MEDIUM" && <span className="p-prio medium">＝</span>}
          {item.priority === "LOW" && <span className="p-prio low">↓</span>}
        </div>
        {item.assignee && (
          <div className="p-task-assignee" title={item.assignee.name}>
            {item.assignee.name.charAt(0)}
          </div>
        )}
      </div>
    </div>
  );
}
