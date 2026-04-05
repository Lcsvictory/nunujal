import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../lib/api";
import { Overlay } from "../../components/Overlay";
import { createProject } from "./api";
import type { CreateProjectPayload } from "./types";

type ProjectCreateOverlayProps = {
  open: boolean;
  onClose: () => void;
  onCreated: (projectId: number, message: string) => Promise<void> | void;
};

const initialFormState: CreateProjectPayload = {
  title: "",
  description: "",
  start_date: "",
  end_date: "",
  join_policy: "LEADER_APPROVE",
};

export function ProjectCreateOverlay({
  open,
  onClose,
  onCreated,
}: ProjectCreateOverlayProps) {
  const [formState, setFormState] = useState<CreateProjectPayload>(initialFormState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setFormState(initialFormState);
      setIsSubmitting(false);
      setErrorMessage(null);
    }
  }, [open]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (!formState.title.trim()) {
      setErrorMessage("프로젝트 이름을 입력하세요.");
      return;
    }

    if (!formState.start_date || !formState.end_date) {
      setErrorMessage("프로젝트 기간을 입력하세요.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await createProject({
        ...formState,
        title: formState.title.trim(),
        description: formState.description.trim(),
      });
      onClose();
      await onCreated(response.project.id, response.message);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "프로젝트 생성 요청을 처리하지 못했습니다.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Overlay
      open={open}
      onClose={onClose}
      title="프로젝트 생성"
      description=""
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

        <label className="field">
          <span>참여 정책</span>
          <select
            value={formState.join_policy}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                join_policy: event.target.value as CreateProjectPayload["join_policy"],
              }))
            }
          >
            <option value="LEADER_APPROVE">팀장 승인 후 참여</option>
            <option value="AUTO_APPROVE">코드 입력 즉시 참여</option>
          </select>
        </label>

        {errorMessage ? <p className="form-feedback form-feedback-error">{errorMessage}</p> : null}

        <div className="overlay-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>
            취소
          </button>
          <button type="submit" className="button button-primary" disabled={isSubmitting}>
            {isSubmitting ? "생성 중..." : "프로젝트 만들기"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}
