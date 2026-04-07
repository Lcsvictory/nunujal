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
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    task: ProjectWorkItemSummary;
  } | null>(null);

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
      // Optimiztic update already ran!
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

  if (loading) return <div className="p-tasks-loading">불러오는 중...</div>;

  return (
    <div className="p-tasks-board-container">
      <div className="p-tasks-header">
        <h2>할일 보드</h2>
        <p className="text-sm text-muted">카드를 드래그하여 상태를 변경하세요.</p>
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
              items={items[status]}
              onAddClick={() => setCreateStatus(status)}
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
    </div>
  );
};

// ====================== Column Component ======================
type KanbanColumnProps = {
  id: TaskStatus;
  title: string;
  items: ProjectWorkItemSummary[];
  onAddClick: () => void;
  onContextMenu: (e: React.MouseEvent, task: ProjectWorkItemSummary) => void;
};

function KanbanColumn({ id, title, items, onAddClick, onContextMenu }: KanbanColumnProps) {
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

      <div className="p-tasks-column-footer">
        <button className="p-tasks-add-btn" onClick={onAddClick}>
          + 할일 추가
        </button>
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
  } = useSortable({ id: item.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <TaskCard item={item} onContextMenu={onContextMenu} />
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
