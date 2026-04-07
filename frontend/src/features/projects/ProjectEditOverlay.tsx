import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../lib/api";
import { Overlay } from "../../components/Overlay";
import { updateProject } from "./api";
import type { UpdateProjectPayload, ProjectDetail } from "./types";

type ProjectEditOverlayProps = {
  open: boolean;
  project: ProjectDetail | null;
  onClose: () => void;
  onUpdated: () => Promise<void> | void;
};

export function ProjectEditOverlay({
  open,
  project,
  onClose,
  onUpdated,
}: ProjectEditOverlayProps) {
  const [formState, setFormState] = useState<UpdateProjectPayload>({
    title: "",
    description: "",
    start_date: "",
    end_date: "",
    join_policy: "LEADER_APPROVE",
    status: "PLANNING",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open && project) {
      setFormState({
        title: project.title,
        description: project.description || "",
        start_date: project.start_date,
        end_date: project.end_date,
        join_policy: project.join_policy as "AUTO_APPROVE" | "LEADER_APPROVE",
        status: project.status,
      });
      setIsSubmitting(false);
      setErrorMessage(null);
    }
  }, [open, project]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!project) return;
    setErrorMessage(null);

    const payloadTitle = formState.title?.trim();
    if (!payloadTitle) {
      setErrorMessage("프로젝트 이름을 입력하세요.");
      return;
    }

    if (!formState.start_date || !formState.end_date) {
      setErrorMessage("프로젝트 기간을 입력하세요.");
      return;
    }

    setIsSubmitting(true);
    try {
      await updateProject(project.id, {
        ...formState,
        title: payloadTitle,
        description: formState.description?.trim(),
      });
      onClose();
      await onUpdated();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "프로젝트 수정 요청을 처리하지 못했습니다.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Overlay
      open={open}
      onClose={onClose}
      title="프로젝트 수정"
      description="프로젝트의 기본 정보를 변경합니다."
    >
      <form className="overlay-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>프로젝트 이름</span>
          <input
            value={formState.title}
            onChange={(event) =>
              setFormState((current) => ({ ...current, title: event.target.value }))
            }
            placeholder="예: 2026 캡스톤 초안 정리"
          />
        </label>

        <label className="field">
          <span>설명</span>
          <textarea
            value={formState.description}
            onChange={(event) =>
              setFormState((current) => ({ ...current, description: event.target.value }))
            }
            placeholder="이 프로젝트에서 무엇을 만들고 검증할지 간단히 적습니다."
            rows={4}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>시작일</span>
            <input
              type="date"
              value={formState.start_date}
              onChange={(event) =>
                setFormState((current) => ({ ...current, start_date: event.target.value }))
              }
            />
          </label>

          <label className="field">
            <span>종료일</span>
            <input
              type="date"
              value={formState.end_date}
              onChange={(event) =>
                setFormState((current) => ({ ...current, end_date: event.target.value }))
              }
            />
          </label>
        </div>

        <div className="field-row">
          <label className="field">
            <span>참여 정책</span>
            <select
              value={formState.join_policy}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  join_policy: event.target.value as UpdateProjectPayload["join_policy"],
                }))
              }
            >
              <option value="LEADER_APPROVE">팀장 승인 후 참여</option>
              <option value="AUTO_APPROVE">코드 입력 즉시 참여</option>
            </select>
          </label>

          <label className="field">
            <span>진행 상태</span>
            <select
              value={formState.status}
              onChange={(event) =>
                setFormState((current) => ({ ...current, status: event.target.value }))
              }
            >
              <option value="PLANNING">계획중</option>
              <option value="IN_PROGRESS">진행중</option>
              <option value="DONE">완료됨</option>
            </select>
          </label>
        </div>

        {errorMessage ? <p className="form-feedback form-feedback-error">{errorMessage}</p> : null}

        <div className="overlay-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>
            취소
          </button>
          <button type="submit" className="button button-primary" disabled={isSubmitting}>
            {isSubmitting ? "수정 중..." : "저장하기"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}
