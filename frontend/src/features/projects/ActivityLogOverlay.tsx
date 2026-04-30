import React, { useState, useEffect, useMemo } from 'react';
import { Overlay } from '../../components/Overlay';
import { apiJsonRequest } from "../../lib/api";
import { fetchProjectWorkItems } from "./api";
import type { ProjectWorkItemSummary } from "./types";

interface ActivityLogOverlayProps {
  projectId: number;
  initialTaskId?: number;
  currentUserId?: number;
  editContext?: any; // The activity object to edit
  onClose: () => void;
  onSuccess: () => void;
}

export function ActivityLogOverlay({ projectId, initialTaskId, currentUserId, editContext, onClose, onSuccess }: ActivityLogOverlayProps) {
  const [tasks, setTasks] = useState<ProjectWorkItemSummary[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  const [selectedCategory, setSelectedCategory] = useState<'BASIC' | 'PEER_SUPPORT' | 'COMMON'>(
    editContext ? editContext.activity_category : 'BASIC'
  );
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>(
    (editContext?.work_items && editContext.work_items.length > 0) ? editContext.work_items.map((w: any) => w.id) : initialTaskId ? [initialTaskId] : []
  );

  const [content, setContent] = useState(editContext ? editContext.content : '');
  
  const initialEv = editContext?.evidences?.[0] || {};
  const [evidenceType, setEvidenceType] = useState(initialEv.evidence_type || 'TEXT');
  const [evidenceDesc, setEvidenceDesc] = useState(initialEv.description || '');
  const [resourceURL, setResourceUrl] = useState(initialEv.resource_url || '');

  const [tags, setTags] = useState<string[]>(
    editContext?.activity_type ? editContext.activity_type.split(',').map((t: string) => t.trim()).filter(Boolean) : []
  );
  const [tagInput, setTagInput] = useState("");

  const addTag = (e?: React.SyntheticEvent) => {
    if (e) e.preventDefault();
    const trimmed = tagInput.trim();
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed]);
    }
    setTagInput("");
  };

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter(t => t !== tagToRemove));
  };

  useEffect(() => {
    fetchProjectWorkItems(projectId).then(res => {
      setTasks(res.items);
      if (initialTaskId) {
        const t = res.items.find(x => x.id === initialTaskId);
        if (t && currentUserId) {
          if (t.assignee && t.assignee.id !== currentUserId) {
             setSelectedCategory('PEER_SUPPORT');
          } else {
             setSelectedCategory('BASIC');
          }
        }
      }
    }).catch(err => console.error("Failed to load tasks for search", err));
  }, [projectId, initialTaskId, currentUserId]);

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      const matchSearch = t.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          (t.assignee?.name.toLowerCase().includes(searchQuery.toLowerCase()));
      if (!matchSearch) return false;
      if (selectedCategory === 'BASIC' && currentUserId) return t.assignee?.id === currentUserId;
      if (selectedCategory === 'PEER_SUPPORT' && currentUserId) return t.assignee?.id !== currentUserId;
      return true;
    });
  }, [tasks, searchQuery, selectedCategory, currentUserId]);

  
  const overlayTitle = editContext ? "활동 내역 수정하기" : "행동 기록 남기기";
  const contentPlaceholder = "어떤 활동을 진행했나요?";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editContext && selectedCategory !== 'COMMON' && selectedTaskIds.length === 0) {
       alert("관련 할일을 선택해주세요.");
       return;
    }

    try {
      const evidences = (evidenceDesc || resourceURL) ? [{
        evidence_type: evidenceType,
        description: evidenceDesc || '',
        resource_url: resourceURL || null
      }] : [];

      if (editContext) {
        await apiJsonRequest(`/api/projects/${projectId}/activities/${editContext.id}`, 'PUT', {
           content,
           activity_category: selectedCategory,
           activity_type: tags.join(', '),
           evidences,
           work_item_ids: selectedCategory === 'COMMON' ? [] : selectedTaskIds,
           target_user_id: selectedCategory === 'PEER_SUPPORT' ? (tasks.find(t => t.id === selectedTaskIds[0])?.assignee?.id || editContext.target_user?.id || null) : null
        });
      } else {
        const payload = {
        work_item_ids: selectedCategory === 'COMMON' ? [] : selectedTaskIds,
        category: selectedCategory,
        target_user_id: selectedCategory === 'PEER_SUPPORT' && tasks.find(t => t.id === selectedTaskIds[0])?.assignee?.id || null,
        activity_type: tags.join(', '),
        contribution_phase: 'FINALIZATION',
        title: 'Task Activity Record',
        content,
        evidences
      };

      await apiJsonRequest(`/api/projects/${projectId}/activities`, 'POST', payload);
      }
      onSuccess();
      onClose();
    } catch (err) {
      console.error(err);
      alert('Failed to submit activity');
    }
  };

  return (
    <Overlay 
      open={true} 
      description="할일의 상태는 할일 페이지에서만 변경 가능합니다." 
      title={overlayTitle} 
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        
        {/* Category Selection */}
        {!initialTaskId && (
          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            기여 유형:
            <select 
              value={selectedCategory} 
              onChange={e => {
                setSelectedCategory(e.target.value as 'BASIC' | 'PEER_SUPPORT' | 'COMMON');
                setSelectedTaskIds([]);
              }} 
              style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc' }}
            >
              <option value="BASIC">내 할일</option>
              <option value="PEER_SUPPORT">팀원 할일 지원</option>
              <option value="COMMON">공통 작업 (할일 매핑 없음)</option>
            </select>
          </label>
        )}

        {/* Task Search & Selection */}
        {selectedCategory !== 'COMMON' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.5rem', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
             <span style={{ fontWeight: 'bold' }}>대상 할일 선택</span>
             {initialTaskId ? (
                <div style={{ padding: '0.5rem', background: '#fff', border: '1px solid #ddd', borderRadius: '4px' }}>
                  {tasks.find(x => x.id === selectedTaskIds[0])?.title || editContext?.work_items?.[0]?.title || '할일 없음'} 
                </div>
             ) : (
                <>
                  <input type="text" placeholder="할일 제목이나 담당자 검색..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }} />
                  <select 
                    value="" 
                    onChange={e => {
                      const val = Number(e.target.value);
                      if (!selectedTaskIds.includes(val)) {
                        setSelectedTaskIds([...selectedTaskIds, val]);
                      }
                    }} 
                    size={4} 
                    style={{ padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
                  >
  <option value="" disabled>할일을 클릭하여 선택하세요...</option>
  {filteredTasks.length === 0 ? <option disabled>조건에 맞는 할일이 없습니다.</option> : null}
  {filteredTasks.map(t => (
    <option key={t.id} value={t.id}>[{t.status}] {t.title} (담당: {t.assignee?.name || '없음'})</option>
  ))}
</select>

{/* 선택된 할일 칩(Pill) 표시 영역 */}
{selectedTaskIds.length > 0 && (
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.5rem' }}>
    {selectedTaskIds.map(id => {
      let t = tasks.find(x => x.id === id);
      if (!t && editContext?.work_items) {
        t = editContext.work_items.find((x: any) => x.id === id);
      }
      if (!t) return null;
      return (
        <div key={id} style={{ display: 'flex', alignItems: 'center', background: '#3b82f6', color: '#ffffff', padding: '0.3rem 0.8rem', borderRadius: '9999px', fontSize: '0.85rem', fontWeight: 'bold', boxShadow: '0 1px 2px rgba(0,0,0,0.1)' }}>
          [{t.status || '상태 없음'}] {t.title}
          <button 
            type="button" 
            onClick={() => setSelectedTaskIds(prev => prev.filter(x => x !== id))}
            style={{ marginLeft: '0.5rem', background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1rem', lineHeight: '1', padding: '0' }}
          >
            &times;
          </button>
        </div>
      );
    })}
  </div>
)}
                </>
             )}
          </div>
        )}

        {/* Action Content */}
        <label>
          활동 내용 (필수):
          <textarea
            required
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={contentPlaceholder}
            style={{ width: '100%', minHeight: '80px', marginTop: '0.5rem', padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
          />
        </label>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.5rem' }}>
          <span style={{ fontWeight: 'bold' }}>활동 성격 태그:</span>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
            {tags.map(tag => (
              <span key={tag} style={{
                background: '#e0e0e0', padding: '0.2rem 0.5rem', borderRadius: '12px', fontSize: '0.9rem',
                display: 'inline-flex', alignItems: 'center', gap: '0.3rem'
              }}>
                #{tag}
                <button type="button" onClick={() => removeTag(tag)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '0', color: '#555', fontWeight: 'bold'
                }}>&times;</button>
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input 
              type="text" 
              value={tagInput} 
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addTag();
                }
              }}
              placeholder="태그 입력 후 Enter" 
              style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', flex: 1 }} 
            />
            <button type="button" onClick={addTag} style={{
              padding: '0.5rem 1rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer'
            }}>
              추가
            </button>
          </div>
        </div>

        {/* Evidence Attachment */}
        <div style={{ padding: '1rem', border: '1px solid #ddd', borderRadius: '4px', backgroundColor: 'transparent' }}>
          <p style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold' }}>증거 자료 첨부 (선택사항)</p>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
             자료 형태:
             <select value={evidenceType} onChange={e => setEvidenceType(e.target.value)} style={{ marginLeft: '0.5rem', padding: '0.2rem' }}>
               <option value="TEXT">텍스트/코드 (직접 입력)</option>
               <option value="LINK">URL 링크 (GitHub PR, Notion 등)</option>
               <option value="FILE">파일/이미지</option>
             </select>
          </label>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
             자료 요약 및 설명:
             <input
               type="text"
               value={evidenceDesc}
               onChange={e => setEvidenceDesc(e.target.value)}
               style={{ width: '100%', marginTop: '0.25rem', padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
             />
          </label>
          {(evidenceType === 'LINK' || evidenceType === 'FILE') && (
            <label style={{ display: 'block' }}>
              첨부 위치 (URL):
              <input
                type="url"
                value={resourceURL}
                onChange={e => setResourceUrl(e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem', padding: '0.5rem', border: '1px solid #ccc', borderRadius: '4px' }}
                placeholder="https://..."
              />
            </label>
          )}
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
          <button type="button" onClick={onClose} style={{ padding: '0.5rem 1rem', cursor: 'pointer' }}>취소</button>
          <button type="submit" style={{ padding: '0.5rem 1rem', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
            저장 및 적용
          </button>
        </div>
      </form>
    </Overlay>
  );
}
