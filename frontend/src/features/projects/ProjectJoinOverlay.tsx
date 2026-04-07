import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../lib/api";
import { Overlay } from "../../components/Overlay";
import { createProjectJoinRequest, previewProjectByJoinCode } from "./api";
import type { JoinPreviewResponse, JoinProjectResponse } from "./types";
import { formatDateRange, formatJoinPolicy, formatProjectStatus } from "./utils";

type ProjectJoinOverlayProps = {
  open: boolean;
  onClose: () => void;
  onJoined: (result: JoinProjectResponse) => Promise<void> | void;
};

export function ProjectJoinOverlay({
  open,
  onClose,
  onJoined,
}: ProjectJoinOverlayProps) {
  const [joinCode, setJoinCode] = useState("");
  const [requestedPositionLabel, setRequestedPositionLabel] = useState("");
  const [requestMessage, setRequestMessage] = useState("");
  const [preview, setPreview] = useState<JoinPreviewResponse | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setJoinCode("");
      setRequestedPositionLabel("");
      setRequestMessage("");
      setPreview(null);
      setIsPreviewLoading(false);
      setIsSubmitting(false);
      setErrorMessage(null);
    }
  }, [open]);

  const handlePreview = async () => {
    if (!joinCode.trim()) {
      setErrorMessage("참여 코드를 먼저 입력하세요.");
      return;
    }

    setErrorMessage(null);
    setIsPreviewLoading(true);
    try {
      const response = await previewProjectByJoinCode(joinCode);
      setPreview(response);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "참여 코드를 확인하지 못했습니다.";
      setPreview(null);
      setErrorMessage(message);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (!joinCode.trim()) {
      setErrorMessage("참여 코드를 입력하세요.");
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await createProjectJoinRequest({
        join_code: joinCode.trim().toUpperCase(),
        requested_position_label: requestedPositionLabel.trim() || undefined,
        request_message: requestMessage.trim() || undefined,
      });
      onClose();
      await onJoined(result);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "프로젝트 참여 요청을 처리하지 못했습니다.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Overlay
      open={open}
      onClose={onClose}
      title="프로젝트 참여"
      description="참여 코드를 확인한 뒤, 현재 화면에서 바로 참여 요청을 보낼 수 있습니다."
    >
      <form className="overlay-form" onSubmit={handleSubmit}>
        <div className="field-row field-row-tight">
          <label className="field">
            <span>참여 코드</span>
            <input
              value={joinCode}
              onChange={(event) => setJoinCode(event.target.value.toUpperCase())}
            />
          </label>

          <button
            type="button"
            className="button button-secondary button-preview"
            onClick={handlePreview}
            disabled={isPreviewLoading}
          >
            {isPreviewLoading ? "확인 중..." : "코드 확인"}
          </button>
        </div>

        {preview ? (
          <section className="preview-card">
            <div className="preview-header">
              <div>
                <strong>{preview.project.title}</strong>
                <p>{preview.project.description || "프로젝트 설명이 아직 없습니다."}</p>
              </div>
              <span className="status-pill">{formatProjectStatus(preview.project.status)}</span>
            </div>
            <dl className="preview-meta">
              <div>
                <dt>기간</dt>
                <dd>{formatDateRange(preview.project.start_date, preview.project.end_date)}</dd>
              </div>
              <div>
                <dt>참여 방식</dt>
                <dd>{formatJoinPolicy(preview.project.join_policy)}</dd>
              </div>
              <div>
                <dt>현재 인원</dt>
                <dd>{preview.project.member_count}명</dd>
              </div>
            </dl>
          </section>
        ) : null}

        <label className="field">
          <span>참여 역할</span>
          <input
            value={requestedPositionLabel}
            onChange={(event) => setRequestedPositionLabel(event.target.value)}
          />
        </label>

        <label className="field">
          <span>요청 메모</span>
          <textarea
            value={requestMessage}
            onChange={(event) => setRequestMessage(event.target.value)}
            rows={4}

          />
        </label>

        {preview?.already_member ? (
          <p className="form-feedback">이미 이 프로젝트에 참여 중입니다.</p>
        ) : null}
        {errorMessage ? <p className="form-feedback form-feedback-error">{errorMessage}</p> : null}

        <div className="overlay-actions">
          <button type="button" className="button button-ghost" onClick={onClose}>
            취소
          </button>
          <button
            type="submit"
            className="button button-primary"
            disabled={isSubmitting || preview?.already_member === true}
          >
            {isSubmitting ? "요청 중..." : "참여 요청 보내기"}
          </button>
        </div>
      </form>
    </Overlay>
  );
}
