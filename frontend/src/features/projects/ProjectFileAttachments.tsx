import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { deleteProjectUpload, prepareProjectUploads, uploadPreparedFile } from "./api";
import type { ProjectUploadedFile } from "./types";

const MAX_TOTAL_BYTES = 50 * 1024 * 1024;

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }
  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)}KB`;
  }
  return `${bytes}B`;
}

type FileUploadPickerProps = {
  projectId: number;
  value: ProjectUploadedFile[];
  onChange: (files: ProjectUploadedFile[]) => void;
  disabled?: boolean;
};

export function FileUploadPicker({
  projectId,
  value,
  onChange,
  disabled = false,
}: FileUploadPickerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const uploadedInThisPicker = useRef<Set<number>>(new Set());
  const [isUploading, setIsUploading] = useState(false);
  const [deletingFileId, setDeletingFileId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleFiles = async (fileList: FileList | null) => {
    const files = Array.from(fileList ?? []);
    if (files.length === 0) return;

    setErrorMessage(null);
    const nextTotalSize = value.reduce((sum, file) => sum + file.file_size_bytes, 0)
      + files.reduce((sum, file) => sum + file.size, 0);
    if (nextTotalSize > MAX_TOTAL_BYTES) {
      setErrorMessage("첨부 파일 전체 용량은 50MB를 넘을 수 없습니다.");
      return;
    }

    setIsUploading(true);
    try {
      const prepared = await prepareProjectUploads(
        projectId,
        files.map((file) => ({
          file_name: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
        })),
      );

      await Promise.all(prepared.items.map((upload, index) => uploadPreparedFile(upload, files[index])));
      const uploadedFiles = prepared.items.map((item) => ({
        id: item.id,
        file_name: item.file_name,
        content_type: item.content_type,
        file_size_bytes: item.file_size_bytes,
        is_image: item.is_image,
        download_url: item.download_url ?? null,
        preview_url: item.preview_url ?? null,
        created_at: item.created_at,
      }));
      uploadedFiles.forEach((file) => uploadedInThisPicker.current.add(file.id));
      onChange([
        ...value,
        ...uploadedFiles,
      ]);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "파일 업로드에 실패했습니다.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveFile = async (file: ProjectUploadedFile) => {
    setErrorMessage(null);

    if (!uploadedInThisPicker.current.has(file.id)) {
      onChange(value.filter((item) => item.id !== file.id));
      return;
    }

    setDeletingFileId(file.id);
    try {
      await deleteProjectUpload(projectId, file.id);
      uploadedInThisPicker.current.delete(file.id);
      onChange(value.filter((item) => item.id !== file.id));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "첨부 파일 삭제에 실패했습니다.");
    } finally {
      setDeletingFileId(null);
    }
  };

  const isBusy = isUploading || deletingFileId !== null;

  return (
    <div className="file-upload-picker">
      <input
        ref={inputRef}
        type="file"
        multiple
        disabled={disabled || isBusy}
        onChange={(event) => void handleFiles(event.target.files)}
      />
      <div className="file-upload-meta">
        <span>전체 50MB 이하</span>
        {isUploading ? <strong>업로드 중...</strong> : null}
        {deletingFileId !== null ? <strong>삭제 중...</strong> : null}
      </div>
      {value.length > 0 ? (
        <div className="file-chip-list">
          {value.map((file) => (
            <button
              key={file.id}
              type="button"
              className="file-chip"
              onClick={() => void handleRemoveFile(file)}
              disabled={disabled || isBusy}
              title="클릭하면 첨부에서 제거됩니다."
            >
              <span>{file.file_name}</span>
              <small>{formatFileSize(file.file_size_bytes)}</small>
            </button>
          ))}
        </div>
      ) : null}
      {errorMessage ? <p className="form-feedback form-feedback-error">{errorMessage}</p> : null}
    </div>
  );
}

type AttachmentListProps = {
  files: ProjectUploadedFile[];
};

export function AttachmentList({ files }: AttachmentListProps) {
  const [previewFile, setPreviewFile] = useState<ProjectUploadedFile | null>(null);

  if (files.length === 0) {
    return <p className="attachment-empty">첨부된 결과물이 없습니다.</p>;
  }

  return (
    <>
      <div className="attachment-list">
        {files.map((file) => (
          <div key={file.id} className="attachment-item">
            {file.is_image && file.preview_url ? (
              <button
                type="button"
                className="attachment-image-button"
                onClick={() => setPreviewFile(file)}
              >
                <img src={file.preview_url} alt={file.file_name} />
              </button>
            ) : null}
            <div className="attachment-item-main">
              <strong>{file.file_name}</strong>
              <span>{formatFileSize(file.file_size_bytes)}</span>
            </div>
            {file.download_url ? (
              <a className="attachment-download-link" href={file.download_url}>
                다운로드
              </a>
            ) : (
              <span className="attachment-download-disabled">다운로드 준비 안됨</span>
            )}
          </div>
        ))}
      </div>

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
    </>
  );
}
