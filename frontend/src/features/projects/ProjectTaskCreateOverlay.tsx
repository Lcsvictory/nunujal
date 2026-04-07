import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../lib/api";
import { Overlay } from "../../components/Overlay";
import { createProjectWorkItem, fetchProjectMembers } from "./api";
import type { CreateProjectWorkItemPayload, ProjectMemberSummary } from "./types";

type TaskStatus = "TODO" | "IN_PROGRESS" | "DONE";

type ProjectTaskCreateOverlayProps = {
  open: boolean;
  onClose: () => void;
  onCreated: () => Promise<void> | void;
  projectId: number;
  initialStatus?: TaskStatus;
};

export function ProjectTaskCreateOverlay({
  open,
  onClose,
  onCreated,
  projectId,
  initialStatus = "TODO",
}: ProjectTaskCreateOverlayProps) {
  const [formState, setFormState] = useState<CreateProjectWorkItemPayload>({
    title: "",
    description: "",
    status: initialStatus,
    priority: "MEDIUM",
    assignee_user_id: null,
    timeline_start_date: "",
    timeline_end_date: "",
  });
  
  const [members, setMembers] = useState<ProjectMemberSummary[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      const now = new Date();
      const end = new Date(now);
      end.setDate(now.getDate() + 1);

      setFormState({
        title: "",
        description: "",
        status: initialStatus,
        priority: "MEDIUM",
        assignee_user_id: null,
        timeline_start_date: now.toISOString().split("T")[0],
        timeline_end_date: end.toISOString().split("T")[0],
      });
      setIsSubmitting(false);
      setErrorMessage(null);
      
      // Load members for assignee dropdown
      fetchProjectMembers(projectId).then(res => {
        setMembers(res.items);
      }).catch(err => {
        console.error("멤버 목록 불러오기 실패", err);
      });
    }
  }, [open, initialStatus, projectId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (!formState.title.trim()) {
      setErrorMessage("할일 제목을 입력하세요.");
      return;
    }

    if (!formState.timeline_start_date || !formState.timeline_end_date) {
      setErrorMessage("시작일과 종료일을 입력하세요.");
      return;
    }

    setIsSubmitting(true);
    try {
      await createProjectWorkItem(projectId, {
        ...formState,
        title: formState.title.trim(),
        description: formState.description.trim(),
      });
      onClose();
      await onCreated();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "할일 생성 요청을 처리하지 못했습니다.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Overlay
      open={open}
      onClose={onClose}
      title="할일 추가"
      description="새로운 할일(태스크)을 생성합니다."
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
          <label className="field">
            <span>진행 상태</span>
            <select
              value={formState.status}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  status: event.target.value as TaskStatus,
                }))
              }
            >
              <option value="TODO">진행 예정</option>
              <option value="IN_PROGRESS">진행 중</option>
              <option value="DONE">완료</option>
            </select>
          </label>

          <label className="field">
            <span>우선순위</span>
            <select
              value={formState.priority}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  priority: event.target.value as CreateProjectWorkItemPayload["priority"],
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
            {isSubmitting ? "저장 중..." : "할일 추가"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}