import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../lib/api";
import { Overlay } from "../../components/Overlay";
import { updateProjectWorkItem, fetchProjectMembers } from "./api";
import type { UpdateProjectWorkItemPayload, ProjectMemberSummary, ProjectWorkItemSummary } from "./types";

type TaskStatus = "TODO" | "IN_PROGRESS" | "DONE";

type ProjectTaskEditOverlayProps = {
  open: boolean;
  onClose: () => void;
  onUpdated: () => Promise<void> | void;
  projectId: number;
  task: ProjectWorkItemSummary | null;
};

export function ProjectTaskEditOverlay({
  open,
  onClose,
  onUpdated,
  projectId,
  task,
}: ProjectTaskEditOverlayProps) {
  const [formState, setFormState] = useState<UpdateProjectWorkItemPayload>({
    title: "",
    description: "",
    status: "TODO",
    priority: "MEDIUM",
    timeline_start_date: "",
    timeline_end_date: "",
  });
  
  const [members, setMembers] = useState<ProjectMemberSummary[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open && task) {
      setFormState({
        title: task.title,
        description: task.description,
        status: task.status,
        priority: task.priority,
        assignee_user_id: task.assignee?.id || null, // Assuming assignee has id
        timeline_start_date: (task as any).timeline_start_date || "",
        timeline_end_date: (task as any).timeline_end_date || "",
      });
      setIsSubmitting(false);
      setErrorMessage(null);
      
      // Load members for assignee dropdown
      fetchProjectMembers(projectId).then(res => {
        setMembers(res.items);
      }).catch(err => {
        console.error("멤버 목록 불러오기 실패", err);
      });
    } else if (!open) {
      setFormState({
        title: "",
        description: "",
        status: "TODO",
        priority: "MEDIUM",
        timeline_start_date: "",
        timeline_end_date: "",
        assignee_user_id: null,
      });
    }
  }, [open, task, projectId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (!formState.title?.trim()) {
      setErrorMessage("할일 제목을 입력하세요.");
      return;
    }

    if (!formState.timeline_start_date || !formState.timeline_end_date) {
      setErrorMessage("시작일과 종료일을 입력하세요.");
      return;
    }

    setIsSubmitting(true);
    try {
      await updateProjectWorkItem(projectId, task!.id, {
        ...formState,
        title: formState.title.trim(),
        description: formState.description?.trim() || "",
      });
      onClose();
      await onUpdated();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "할일 수정 요청을 처리하지 못했습니다.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!task) return null;

  return (
    <Overlay
      open={open}
      onClose={onClose}
      title="할일 수정"
      description={`${task.title} 태스크 정보를 수정합니다.`}
    >
      <form className="overlay-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>할일 제목</span>
          <input
            autoFocus
            value={formState.title}
            onChange={(event) =>
              setFormState((current) => ({ ...current, title: event.target.value }))
            }
            placeholder="할일의 제목을 입력하세요"
          />
        </label>

        <label className="field">
          <span>설명</span>
          <textarea
            value={formState.description}
            onChange={(event) =>
              setFormState((current) => ({ ...current, description: event.target.value }))
            }
            placeholder="상세 내용을 작성하세요."
            rows={4}
          />
        </label>

        <div className="field-row">
          {/* <label className="field">
            <span>진행 상태</span>
            <select
              value={formState.status}
              disabled={task?.status === "DONE"}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  status: event.target.value as TaskStatus,
                }))
              }
            >
              <option value="TODO">진행 예정</option>
              <option value="IN_PROGRESS">진행 중</option>
              {task?.status === "DONE" && <option value="DONE">완료</option>}
            </select>
            {task?.status === "DONE" ? (
              <p style={{ fontSize: "12px", color: "#666", marginTop: "4px", margin: "0" }}>
                완료된 할일은 상태를 변경할 수 없습니다.
              </p>
            ) : (
              <p style={{ fontSize: "12px", color: "#666", marginTop: "4px", margin: "0" }}>
                할일 완료 처리는 보드에서만 가능합니다.
              </p>
            )}
          </label> */}

          <label className="field">
            <span>우선순위</span>
            <select
              value={formState.priority}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  priority: event.target.value as UpdateProjectWorkItemPayload["priority"],
                }))
              }
            >
              <option value="HIGH">높음</option>
              <option value="MEDIUM">보통</option>
              <option value="LOW">낮음</option>
            </select>
          </label>
        </div>

        <div className="field-row">
          <label className="field">
            <span>시작일</span>
            <input
              type="date"
              value={formState.timeline_start_date}
              onChange={(event) =>
                setFormState((current) => ({ ...current, timeline_start_date: event.target.value }))
              }
            />
          </label>

          <label className="field">
            <span>종료일</span>
            <input
              type="date"
              value={formState.timeline_end_date}
              onChange={(event) =>
                setFormState((current) => ({ ...current, timeline_end_date: event.target.value }))
              }
            />
          </label>
        </div>

        <label className="field">
          <span>담당자</span>
          <select
            value={formState.assignee_user_id || ""}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                assignee_user_id: event.target.value ? Number(event.target.value) : null,
              }))
            }
          >
            <option value="">(없음)</option>
            {members.map(member => (
              <option key={member.user_id} value={member.user_id}>
                {member.name} ({member.project_role})
              </option>
            ))}
          </select>
        </label>

        {errorMessage ? <p className="form-feedback form-feedback-error">{errorMessage}</p> : null}

        <div className="overlay-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>
            취소
          </button>
          <button type="submit" className="button button-primary" disabled={isSubmitting}>
            {isSubmitting ? "저장 중..." : "수정 완료"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}