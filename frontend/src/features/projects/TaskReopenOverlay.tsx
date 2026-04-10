import React, { useState } from 'react';
import { Overlay } from '../../components/Overlay';
import { apiJsonRequest } from "../../lib/api";
import type { ProjectWorkItemSummary } from "./types";

interface TaskReopenOverlayProps {
  projectId: number;
  task: ProjectWorkItemSummary;
  targetStatus: 'TODO' | 'IN_PROGRESS';
  onClose: () => void;
  onSuccess: () => void;
}

export function TaskReopenOverlay({ projectId, task, targetStatus, onClose, onSuccess }: TaskReopenOverlayProps) {
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      alert("사유를 입력해주세요.");
      return;
    }
    
    setIsSubmitting(true);
    try {
      const payload = {
        work_item_ids: [task.id],
        category: 'BASIC',
        activity_type: 'FINALIZATION',
        contribution_phase: 'FINALIZATION',
        title: `작업 재개: ${targetStatus === 'IN_PROGRESS' ? '진행 중' : '진행 예정'}으로 변경`,
        content: `워크 아이템 정보가 ${targetStatus === 'IN_PROGRESS' ? '진행 중' : '진행 예정'}으로 변경되었습니다.\n\n재개 사유: ${reason}`,
        target_task_status: targetStatus,
        evidences: []
      };

      await apiJsonRequest(`/api/projects/${projectId}/activities`, 'POST', payload);
      onSuccess();
    } catch (err) {
      console.error(err);
      alert('상태 변경 및 사유 기록에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Overlay 
      open={true} 
      title="완료된 할일 다시 열기" 
      description="이미 완료된 할일을 다시 진행 상태로 되돌리는 이유를 남겨주세요." 
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ padding: '0.5rem', background: '#f9f9f9', border: '1px solid #ddd', borderRadius: '4px' }}>
          <strong>대상 할일:</strong> {task.title}
        </div>

        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <span style={{ fontWeight: 'bold' }}>상태 변경 사유 (필수):</span>
          <textarea
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="어떤 이유로 작업을 재개하는지 자세히 적어주세요. 이 내용은 활동 피드에 시스템 기록으로 남습니다."
            style={{ width: '100%', minHeight: '100px', padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
          />
        </label>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
          <button type="button" onClick={onClose} disabled={isSubmitting} style={{ padding: '0.5rem 1rem', cursor: 'pointer' }}>취소</button>
          <button type="submit" disabled={isSubmitting} style={{ padding: '0.5rem 1rem', background: '#eab308', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
            할일 상태 변경
          </button>
        </div>
      </form>
    </Overlay>
  );
}
