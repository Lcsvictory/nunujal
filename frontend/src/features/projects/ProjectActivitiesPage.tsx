import React, { useState } from 'react';
import './ProjectActivitiesPage.css';
import { ActivityLogOverlay } from './ActivityLogOverlay';
import { apiJsonRequest } from "../../lib/api";
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

  const [editContent, setEditContent] = useState('');

  const currentUserId = project.members.find(m => m.project_member_id === project.my_membership?.project_member_id)?.user_id;

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
          <h2>활동 히스토리 (Feed)</h2>
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
            
            return (
              <div key={activity.id} className="activity-card" style={{ position: 'relative' }}>
                {isMine && (
                  <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', gap: '5px' }}>
                    <button onClick={() => { setEditingActivity(activity); setEditContent(activity.content); }} style={{ fontSize: '0.8rem', padding: '2px 5px', cursor: 'pointer' }}>수정</button>
                    <button onClick={() => handleDelete(activity.id)} style={{ fontSize: '0.8rem', padding: '2px 5px', cursor: 'pointer', color: 'red' }}>삭제</button>
                  </div>
                )}
                <div className="activity-card-header">
                  <span className={`activity-badge ${config.colorClass}`}>
                    {config.label}
                  </span>
                  <span className="activity-time">{new Date(activity.occurred_at).toLocaleString()}</span>
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
                          onClick={() => alert(`[할일 정보]\n제목: ${w.title}`)}
                        >
                          📌 {w.title}
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
    </div>
  );
}
