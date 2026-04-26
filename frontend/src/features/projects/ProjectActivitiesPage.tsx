import React, { useState, useEffect } from 'react';
import './ProjectActivitiesPage.css';
import { ActivityLogOverlay } from './ActivityLogOverlay';
import { ProjectTaskEditOverlay } from './ProjectTaskEditOverlay';
import { apiJsonRequest } from "../../lib/api";
import { fetchProjectWorkItems, toggleActivityReaction } from "./api";
import type { ProjectDetail } from './types';

type ProjectActivitiesPageProps = {
  project: ProjectDetail;
  onRefresh?: () => void;
};

// --- [Component] ---
export function ProjectActivitiesPage({ project, onRefresh }: ProjectActivitiesPageProps) {
  const [filterAuthor, setFilterAuthor] = useState<'ALL' | 'ME'>('ALL');
  const [filterType, setFilterType] = useState<'ALL' | string>('ALL');
  
  const [isActivityOverlayOpen, setIsActivityOverlayOpen] = useState(false);
  const [editingActivity, setEditingActivity] = useState<any>(null); // Quick modal for editing
  const [hoveredTask, setHoveredTask] = useState<any>(null); // Small popup for task info
  const [popupPos, setPopupPos] = useState({ x: 0, y: 0 });

  const [editContent, setEditContent] = useState('');
  const [allTasks, setAllTasks] = useState<any[]>([]);

  useEffect(() => {
    fetchProjectWorkItems(project.id).then(res => {
      setAllTasks(res.items);
    }).catch(err => console.error(err));
  }, [project.id]);

  const currentUserId = project.members.find(m => m.project_member_id === project.my_membership?.project_member_id)?.user_id;

  const handleToggleReaction = async (activityId: number, reactionType: "CONFIRMED" | "HELPFUL" | "AWESOME") => {
    try {
      await toggleActivityReaction(project.id, activityId, reactionType);
      if (onRefresh) onRefresh();
    } catch (e: any) {
      alert(e.message || "Failed to toggle reaction");
    }
  };

  const activities = project.overview.recent_activities || [];

  // 필터 적용 로직
  const filteredActivities = activities.filter((activity) => {
    if (filterAuthor === 'ME' && activity.actor.id !== currentUserId) return false;
    if (filterType !== 'ALL' && activity.activity_category !== filterType) return false;
    return true;
  });

  const getTypeConfig = (category: string) => {
    switch (category) {
      case 'BASIC':
        return { label: '내 할일', colorClass: 'badge-basic' };
      case 'PEER_SUPPORT':
        return { label: '팀원 기여', colorClass: 'badge-peer' };
      case 'COMMON':
        return { label: '공통 작업', colorClass: 'badge-common' };
      default:
        return { label: '기타', colorClass: 'badge-common' };
    }
  };

  const handleDelete = async (activityId: number) => {
    if (!window.confirm("이 활동을 삭제하시겠습니까?")) return;
    try {
      await apiJsonRequest(`/api/projects/${project.id}/activities/${activityId}`, 'DELETE', null);
      if (onRefresh) onRefresh();
    } catch(err) {
      alert("삭제 실패");
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingActivity) return;
    try {
      await apiJsonRequest(`/api/projects/${project.id}/activities/${editingActivity.id}`, 'PUT', {
        content: editContent
      });
      setEditingActivity(null);
      if (onRefresh) onRefresh();
    } catch(err) {
      alert("수정 실패");
    }
  };

  return (
    <div className="activities-page-container">
      <header className="activities-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>활동</h2>
          <p>프로젝트 내 모든 활동과 기여 내역을 모아봅니다.</p>
        </div>
        <button 
          onClick={() => setIsActivityOverlayOpen(true)}
          style={{ padding: '0.8rem 1.2rem', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
        >
          + 활동/기여 기록하기
        </button>
      </header>

      {/* 필터 영역 */}
      <div className="activities-filters">
        <div className="filter-group">
          <span className="filter-label">작성자:</span>
          <button 
            className={`filter-btn ${filterAuthor === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterAuthor('ALL')}
          >전체 보기</button>
          <button 
            className={`filter-btn ${filterAuthor === 'ME' ? 'active' : ''}`}
            onClick={() => setFilterAuthor('ME')}
          >내 활동만 보기</button>
        </div>

        <div className="filter-group">
          <span className="filter-label">유형:</span>
          <button 
            className={`filter-btn ${filterType === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterType('ALL')}
          >전체</button>
          <button 
            className={`filter-btn ${filterType === 'BASIC' ? 'active' : ''}`}
            onClick={() => setFilterType('BASIC')}
          >내 할일</button>
          <button 
            className={`filter-btn ${filterType === 'PEER_SUPPORT' ? 'active' : ''}`}
            onClick={() => setFilterType('PEER_SUPPORT')}
          >팀원 기여</button>
          <button 
            className={`filter-btn ${filterType === 'COMMON' ? 'active' : ''}`}
            onClick={() => setFilterType('COMMON')}
          >공통 작업</button>
        </div>
      </div>

      {/* 피드 리스트 영역 */}
      <div className="activities-list">
        {filteredActivities.length === 0 ? (
          <div className="empty-state">해당하는 활동 기록이 없습니다.</div>
        ) : (
          filteredActivities.map((activity) => {
            const config = getTypeConfig(activity.activity_category);
            const isMine = activity.actor.id === currentUserId;
            const isModified = activity.updated_at && new Date(activity.updated_at) > new Date(activity.occurred_at);
            
            return (
              <div key={activity.id} className="activity-card" style={{ position: 'relative', marginTop: "1rem" }}>
                <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', gap: '5px', zIndex: 10 }}>
                  {isMine && (
                    <>
                      <button onClick={(e) => { e.stopPropagation(); setEditingActivity(activity); setEditContent(activity.content); }} style={{ fontSize: '0.8rem', padding: '4px 8px', cursor: 'pointer', background: '#f3f4f6', color: '#374151', border: '1px solid #d1d5db', borderRadius: '4px', fontWeight: 'bold' }}>수정</button>
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(activity.id); }} style={{ fontSize: '0.8rem', padding: '4px 8px', cursor: 'pointer', background: '#fee2e2', color: '#dc2626', border: '1px solid #fca5a5', borderRadius: '4px', fontWeight: 'bold' }}>삭제</button>
                    </>
                  )}
                  {activity.activity_category === 'PEER_SUPPORT' && activity.review_state === 'UNDER_REVIEW' && activity.target_user?.id === currentUserId && (
                    <button 
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          await apiJsonRequest(`/api/projects/${project.id}/activities/${activity.id}/approve`, "POST", {});
                          if (onRefresh) onRefresh();
                        } catch(e) {
                          alert("승인 실패");
                        }
                      }} 
                      style={{ fontSize: '0.8rem', padding: '4px 8px', cursor: 'pointer', background: '#10b981', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold' }}>
                      ✓ 승인
                    </button>
                  )}
                </div>
                <div className="activity-card-header" style={{ position: 'relative', minHeight: '30px' }}>
                  <span className={`activity-badge ${config.colorClass}`}>
                    {config.label}
                  </span>
                </div>
                
                <div className="activity-card-body">
                  <strong>{activity.actor.name}</strong>님이 
                  {activity.activity_category === 'PEER_SUPPORT' && activity.target_user && (
                    <span className="highlight-target"> {activity.target_user.name}님 의 </span>
                  )}
                                    {(activity.work_items && activity.work_items.length > 0) ? (
                    <span style={{ margin: '0 0.4rem' }}>
                      {activity.work_items.map((w: any) => (
                        <span 
                          key={w.id}
                          style={{ display: 'inline-flex', alignItems: 'center', background: '#e0e7ff', color: '#4338ca', padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.85rem', fontWeight: 'bold', cursor: 'pointer', marginRight: '0.4rem', border: '1px solid #c7d2fe', transition: 'all 0.2s', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }} 
                          title="클릭하여 할일 정보 보기"
                          onClick={(e) => {
                            const rect = e.currentTarget.getBoundingClientRect();
                            setPopupPos({ x: rect.left + window.scrollX, y: rect.bottom + window.scrollY + 10 });
                            setHoveredTask(w);
                          }}
                        >
                          {w.title}
                        </span>
                      ))}
                    </span>
                  ) : (
                    <span> 다음 활동을 기록했습니다: </span>
                  )}
                  {(activity.work_items && activity.work_items.length > 0) && <span>작업을 위해: </span>}
                  <p className="activity-content">"{activity.content}"</p>

                  {activity.evidences && activity.evidences.length > 0 && (
                    <div style={{ marginTop: '0.8rem', padding: '0.8rem', backgroundColor: '#f3f4f6', borderRadius: '4px', fontSize: '0.9rem' }}>
                      <strong style={{ display: 'block', marginBottom: '0.4rem', color: '#4b5563' }}>첨부된 증거 자료:</strong>
                      {activity.evidences.map((ev: any, idx: number) => (
                        <div key={idx} style={{ marginBottom: '0.4rem' }}>
                          <span style={{ display: 'inline-block', padding: '2px 6px', backgroundColor: '#e5e7eb', borderRadius: '4px', marginRight: '6px', fontSize: '0.8rem' }}>
                            {ev.evidence_type}
                          </span>
                          <span>{ev.description}</span>
                          {ev.resource_url && (
                             <div style={{ marginTop: '0.2rem', paddingLeft: '0.5rem', borderLeft: '2px solid #ccc' }}>
                               <a href={ev.resource_url} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'none' }}>
                                 {ev.resource_url}
                               </a>
                             </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: '1rem', borderTop: '1px solid #f3f4f6', paddingTop: '0.8rem' }}>
                  <div className="activity-tags-and-reactions" style={{ display: 'flex', gap: '0.8rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div className="activity-tags" style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                      {activity.activity_type.split(',').map((t: string) => t.trim()).filter(Boolean).map((t: string) => (
                        <span key={t} style={{ background: '#e0e7ff', color: '#4338ca', padding: '0.2rem 0.5rem', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold' }}>
                          #{t}
                        </span>
                      ))}
                    </div>
                    {/* Reactions */}
                    <div className="activity-reactions" style={{ display: 'flex', gap: '0.4rem' }}>
                      {[
                        { type: 'CONFIRMED', icon: '👍', label: '인정함' },
                        { type: 'HELPFUL', icon: '🙏', label: '큰 도움' },
                        { type: 'AWESOME', icon: '🔥', label: '훌륭해요' }
                      ].map(rx => {
                        const count = activity.reactions?.filter(r => r.reaction_type === rx.type).length || 0;
                        const hasReacted = activity.reactions?.some(r => r.reaction_type === rx.type && r.reactor_user_id === currentUserId);
                        return (
                          <button
                            key={rx.type}
                            onClick={() => handleToggleReaction(activity.id, rx.type as any)}
                            style={{
                              background: hasReacted ? '#fee2e2' : '#f3f4f6',
                              color: hasReacted ? '#b91c1c' : '#4b5563',
                              border: `1px solid ${hasReacted ? '#fca5a5' : '#e5e7eb'}`,
                              padding: '0.2rem 0.5rem',
                              borderRadius: '12px',
                              fontSize: '0.75rem',
                              fontWeight: 'bold',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.2rem'
                            }}
                          >
                            <span>{rx.icon}</span>
                            <span>{rx.label}</span>
                            {count > 0 && <span style={{ marginLeft: '0.2rem' }}>{count}</span>}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.2rem' }}>
                    {isModified ? (
                      <span style={{ fontSize: '0.8rem', color: '#6b7280', fontWeight: 'bold' }}>
                        {new Date(activity.updated_at).toLocaleString()} (수정됨)
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.8rem', color: '#6b7280', fontWeight: 'bold' }}>
                        {new Date(activity.occurred_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
      
      {isActivityOverlayOpen && (
        <ActivityLogOverlay
          projectId={project.id}
          currentUserId={currentUserId}
          onClose={() => setIsActivityOverlayOpen(false)}
          onSuccess={() => {
            setIsActivityOverlayOpen(false);
            if (onRefresh) onRefresh();
          }}
        />
      )}

      {editingActivity && (
        <ActivityLogOverlay
          projectId={project.id}
          currentUserId={currentUserId}
          editContext={editingActivity}
          onClose={() => setEditingActivity(null)}
          onSuccess={() => {
            setEditingActivity(null);
            if (onRefresh) onRefresh();
          }}
        />
      )}

      {hoveredTask && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 999 }} onClick={() => setHoveredTask(null)}>
          <div 
            style={{ 
              position: 'absolute', top: popupPos.y, left: popupPos.x, background: '#fff', 
              border: '1px solid #ddd', borderRadius: '8px', padding: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', 
              zIndex: 1000, width: '280px', pointerEvents: 'auto' 
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <h4 style={{ margin: 0, fontSize: '14px', color: '#111' }}>{hoveredTask.title}</h4>
              <button 
                onClick={() => setHoveredTask(null)} 
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px', color: '#888', padding: 0 }}
              >&times;</button>
            </div>
            
            {(() => {
               const detail = allTasks.find(t => t.id === hoveredTask.id);
               return detail ? (
                 <div style={{ fontSize: '12px', color: '#444' }}>
                   {detail.description && <p style={{ margin: '0 0 8px 0' }}>{detail.description}</p>}
                   <div style={{ background: '#f5f5f5', padding: '6px', borderRadius: '4px' }}>
                     {(detail.timeline_start_date || detail.timeline_end_date) && (
                       <p style={{ margin: 0 }}><strong>기간:</strong> {detail.timeline_start_date || '?'} ~ {detail.timeline_end_date || '?'}</p>
                     )}
                   </div>
                 </div>
               ) : (
                 <p style={{ fontSize: '12px', color: '#666', margin: 0 }}>데이터를 불러오는 중입니다...</p>
               );
            })()}
          </div>
        </div>
      )}
    </div>
  );
}
