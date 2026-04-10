import React, { useState } from 'react';
import './ProjectActivitiesPage.css';

// --- [Mock Data & Types] ---
type ActivityType = 'BASIC' | 'PEER_SUPPORT' | 'COMMON';

interface Activity {
  id: string;
  type: ActivityType;
  author: string;
  targetUser?: string;
  targetTask?: string;
  content: string;
  createdAt: string;
  status?: 'PENDING' | 'APPROVED'; // 협업 기여 승인 상태
}

const MOCK_ACTIVITIES: Activity[] = [
  {
    id: '1',
    type: 'PEER_SUPPORT',
    author: '나(진수)',
    targetUser: '민지',
    targetTask: 'DB 스키마 설계',
    content: '외래키 매핑 과정에서 발생한 순환 참조 에러를 함께 디버깅하며 해결했습니다.',
    createdAt: '2시간 전',
    status: 'APPROVED',
  },
  {
    id: '2',
    type: 'BASIC',
    author: '민지',
    targetTask: 'API 라우터 초기 세팅',
    content: 'User 관련 CRUD API 라우팅을 완료했습니다.',
    createdAt: '4시간 전',
  },
  {
    id: '3',
    type: 'COMMON',
    author: '상훈',
    content: '오프라인 킥오프 회의 기록 및 노션 초기 페이지 세팅 완료',
    createdAt: '어제',
  },
  {
    id: '4',
    type: 'BASIC',
    author: '나(진수)',
    targetTask: '인증 미들웨어 구현',
    content: 'JWT 토큰 기반 로그인 미들웨어 초안 작성 완료',
    createdAt: '어제',
  },
];

// --- [Component] ---
export function ProjectActivitiesPage() {
  const [filterAuthor, setFilterAuthor] = useState<'ALL' | 'ME'>('ALL');
  const [filterType, setFilterType] = useState<'ALL' | ActivityType>('ALL');

  // 필터 적용 로직
  const filteredActivities = MOCK_ACTIVITIES.filter((activity) => {
    if (filterAuthor === 'ME' && activity.author !== '나(진수)') return false;
    if (filterType !== 'ALL' && activity.type !== filterType) return false;
    return true;
  });

  // 타입별 UI 렌더링 헬퍼
  const getTypeConfig = (type: ActivityType) => {
    switch (type) {
      case 'BASIC':
        return { label: '📝 내 할일 진행', colorClass: 'badge-basic' };
      case 'PEER_SUPPORT':
        return { label: '🤝 팀원 지원 (기여)', colorClass: 'badge-peer' };
      case 'COMMON':
        return { label: '🌐 공통 작업', colorClass: 'badge-common' };
    }
  };

  return (
    <div className="activities-page-container">
      <header className="activities-header">
        <h1>**미완성입니다** </h1>
        <h2>활동 히스토리 (Feed)</h2>
        <p>프로젝트 내 모든 활동과 기여 내역을 모아봅니다.</p>
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
          >👤 내 활동만 보기</button>
        </div>

        <div className="filter-group">
          <span className="filter-label">유형:</span>
          <button 
            className={`filter-btn ${filterType === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterType('ALL')}
          >전체 기여</button>
          <button 
            className={`filter-btn ${filterType === 'BASIC' ? 'active' : ''}`}
            onClick={() => setFilterType('BASIC')}
          >📝 기본</button>
          <button 
            className={`filter-btn ${filterType === 'PEER_SUPPORT' ? 'active' : ''}`}
            onClick={() => setFilterType('PEER_SUPPORT')}
          >🤝 협업(지원)</button>
          <button 
            className={`filter-btn ${filterType === 'COMMON' ? 'active' : ''}`}
            onClick={() => setFilterType('COMMON')}
          >🌐 공통</button>
        </div>
      </div>

      {/* 피드 리스트 영역 */}
      <div className="activities-list">
        {filteredActivities.length === 0 ? (
          <div className="empty-state">해당하는 활동 기록이 없습니다.</div>
        ) : (
          filteredActivities.map((activity) => {
            const config = getTypeConfig(activity.type);
            return (
              <div key={activity.id} className="activity-card">
                <div className="activity-card-header">
                  <span className={`activity-badge ${config.colorClass}`}>
                    {config.label}
                  </span>
                  <span className="activity-time">{activity.createdAt}</span>
                </div>
                
                <div className="activity-card-body">
                  <strong>{activity.author}</strong>님이 
                  {activity.type === 'PEER_SUPPORT' && activity.targetUser && (
                    <span className="highlight-target"> {activity.targetUser}님의 </span>
                  )}
                  {activity.targetTask ? (
                    <span> [<strong>{activity.targetTask}</strong>] 작업을 위해: </span>
                  ) : (
                    <span> 다음 활동을 기록했습니다: </span>
                  )}
                  <p className="activity-content">"{activity.content}"</p>
                </div>

                {/* 협업 기여일 경우 상태 표시 (소셜 프루프) */}
                {activity.type === 'PEER_SUPPORT' && (
                  <div className="activity-card-footer">
                    {activity.status === 'APPROVED' ? (
                      <span className="status-approved">✅ {activity.targetUser}님이 기여를 인정했습니다.</span>
                    ) : (
                      <span className="status-pending">⏳ {activity.targetUser}님의 확인 대기 중...</span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
