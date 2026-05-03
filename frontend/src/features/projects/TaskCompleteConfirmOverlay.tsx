import React, { useState } from "react";
import { Overlay } from "../../components/Overlay";
import { updateProjectWorkItem } from "./api";
import type { ProjectWorkItemSummary } from "./types";

type TaskCompleteConfirmOverlayProps = {
  projectId: number;
  task: ProjectWorkItemSummary;
  onClose: () => void;
  onSuccess: () => void;
};

export function TaskCompleteConfirmOverlay({
  projectId,
  task,
  onClose,
  onSuccess,
}: TaskCompleteConfirmOverlayProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleConfirm = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await updateProjectWorkItem(projectId, task.id, {
        status: "DONE",
      });
      onSuccess();
    } catch (error) {
      console.error(error);
      alert("할일을 완료 처리하지 못했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Overlay
      open
      title="할일 완료 확인"
      description="완료 처리하면 이 할일은 완료 목록으로 이동합니다. 실제 작업이 끝났는지 다시 확인하세요."
      onClose={onClose}
    >
      <form className="overlay-form" onSubmit={handleConfirm}>
        <div className="task-status-confirm-card">
          <span>완료할 할일</span>
          <strong>{task.title}</strong>
          {task.description ? <p>{task.description}</p> : null}
        </div>

        <div className="task-status-confirm-warning">
          끝나지 않은 작업을 완료로 옮기면 팀의 진행률과 기여도 판단에 영향을 줄 수 있습니다.
        </div>

        <div className="overlay-actions">
          <button type="button" className="button button-ghost" onClick={onClose} disabled={isSubmitting}>
            취소
          </button>
          <button type="submit" className="button button-primary" disabled={isSubmitting}>
            {isSubmitting ? "완료 처리 중..." : "완료로 이동"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}
