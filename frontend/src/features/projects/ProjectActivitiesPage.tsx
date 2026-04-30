import React, { useState, useEffect, useMemo } from 'react';
import './ProjectActivitiesPage.css';
import { ActivityLogOverlay } from './ActivityLogOverlay';
import { ApiError, apiJsonRequest } from "../../lib/api";
import { fetchProjectActivities, fetchProjectWorkItems, toggleActivityReaction } from "./api";
import type { ProjectActivityListFilters, ProjectRecentActivity, ProjectDetail } from './types';

type ProjectActivitiesPageProps = {
  project: ProjectDetail;
  onRefresh?: () => void;
};

const PAGE_LIMIT = 30;
const ALL = "ALL";

const todayString = () => new Date().toISOString().slice(0, 10);

const daysAgoString = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
};

// --- [Component] ---
export function ProjectActivitiesPage({ project, onRefresh }: ProjectActivitiesPageProps) {
  const activityFilterRef = React.useRef<HTMLDivElement | null>(null);
  const [filters, setFilters] = useState<ProjectActivityListFilters>({
    author_scope: "ALL",
    category: ALL,
    review_state: ALL,
    contribution_phase: ALL,
    credibility_level: ALL,
    source_type: "MANUAL",
    evidence_type: ALL,
    reaction_type: ALL,
    filter_operator: "AND",
    limit: PAGE_LIMIT,
    offset: 0,
  });
  const [activities, setActivities] = useState<ProjectRecentActivity[]>([]);
  const [activityTotal, setActivityTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [isLoadingActivities, setIsLoadingActivities] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  
  const [isActivityOverlayOpen, setIsActivityOverlayOpen] = useState(false);
  const [editingActivity, setEditingActivity] = useState<any>(null); // Quick modal for editing
  const [hoveredTask, setHoveredTask] = useState<any>(null); // Small popup for task info
  const [popupPos, setPopupPos] = useState({ x: 0, y: 0 });

  const [allTasks, setAllTasks] = useState<any[]>([]);
  const [taskFilterSearch, setTaskFilterSearch] = useState("");
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([]);
  const [isTaskDropdownOpen, setIsTaskDropdownOpen] = useState(false);

  useEffect(() => {
    fetchProjectWorkItems(project.id).then(res => {
      setAllTasks(res.items);
    }).catch(err => console.error(err));
  }, [project.id]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!activityFilterRef.current?.contains(event.target as Node)) {
        setIsTaskDropdownOpen(false);
      }
    };
    window.addEventListener("mousedown", handleClickOutside);
    return () => window.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const currentUserId = project.members.find(m => m.project_member_id === project.my_membership?.project_member_id)?.user_id;

  const taskSearchTerms = useMemo(() => {
    return taskFilterSearch
      .split(",")
      .map((term) => term.trim().toLowerCase())
      .filter(Boolean);
  }, [taskFilterSearch]);

  const matchedTaskIds = useMemo(() => {
    if (selectedTaskIds.length > 0 || taskSearchTerms.length === 0) {
      return [];
    }
    return allTasks
      .filter((task) => {
        const title = String(task.title ?? "").toLowerCase();
        return taskSearchTerms.some((term) => title.includes(term));
      })
      .map((task) => task.id);
  }, [allTasks, selectedTaskIds.length, taskSearchTerms]);

  const activeFilters = useMemo(() => ({
    ...filters,
    work_item_id: undefined,
    work_item_ids: selectedTaskIds.length > 0
      ? selectedTaskIds.join(",")
      : taskSearchTerms.length === 0
        ? undefined
        : (matchedTaskIds.length > 0 ? matchedTaskIds.join(",") : "0"),
    limit: PAGE_LIMIT,
  }), [filters, matchedTaskIds, selectedTaskIds, taskSearchTerms.length]);

  const loadActivities = async (options?: { append?: boolean; offset?: number }) => {
    const nextOffset = options?.offset ?? (options?.append ? activities.length : 0);
    setIsLoadingActivities(true);
    setActivityError(null);
    try {
      const response = await fetchProjectActivities(project.id, {
        ...activeFilters,
        offset: nextOffset,
        limit: PAGE_LIMIT,
      });
      setActivities((current) => options?.append ? [...current, ...response.items] : response.items);
      setActivityTotal(response.total);
      setHasMore(response.has_more);
    } catch (error) {
      setActivityError(error instanceof ApiError ? error.message : "활동 목록을 불러오지 못했습니다.");
    } finally {
      setIsLoadingActivities(false);
    }
  };

  useEffect(() => {
    void loadActivities({ offset: 0 });
  }, [project.id, activeFilters]);

  const updateFilter = (patch: ProjectActivityListFilters) => {
    setFilters((current) => ({ ...current, ...patch, offset: 0 }));
  };

  const resetFilters = () => {
    setTaskFilterSearch("");
    setSelectedTaskIds([]);
    setIsTaskDropdownOpen(false);
    setFilters({
      author_scope: "ALL",
      category: ALL,
      review_state: ALL,
      contribution_phase: ALL,
      credibility_level: ALL,
      source_type: "MANUAL",
      evidence_type: ALL,
      reaction_type: ALL,
      filter_operator: "AND",
      limit: PAGE_LIMIT,
      offset: 0,
    });
  };

  const setDatePreset = (days: number | null) => {
    updateFilter({
      date_from: days === null ? undefined : daysAgoString(days),
      date_to: days === null ? undefined : todayString(),
    });
  };

  const reloadActivitiesAndOverview = async () => {
    await loadActivities({ offset: 0 });
    if (onRefresh) onRefresh();
  };

  const handleToggleReaction = async (activityId: number, reactionType: "CONFIRMED" | "HELPFUL" | "AWESOME") => {
    try {
      await toggleActivityReaction(project.id, activityId, reactionType);
      await reloadActivitiesAndOverview();
    } catch (e: any) {
      alert(e.message || "Failed to toggle reaction");
    }
  };

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
      await reloadActivitiesAndOverview();
    } catch(err) {
      alert("삭제 실패");
    }
  };

  const selectedAuthorValue = filters.author_scope === "ME"
    ? "ME"
    : filters.actor_user_id
      ? String(filters.actor_user_id)
      : ALL;

  const authorOptions = project.members.filter((member) => member.user_id !== currentUserId);

  const selectedDatePreset = !filters.date_from && !filters.date_to
    ? ALL
    : filters.date_from === daysAgoString(7) && filters.date_to === todayString()
      ? "7"
      : filters.date_from === daysAgoString(30) && filters.date_to === todayString()
        ? "30"
        : ALL;

  const taskOptions = useMemo(() => {
    const selectedIdSet = new Set(selectedTaskIds);
    if (taskSearchTerms.length === 0) {
      return [];
    }
    return allTasks.filter((task) => {
      const title = String(task.title ?? "").toLowerCase();
      return !selectedIdSet.has(task.id) && taskSearchTerms.some((term) => title.includes(term));
    });
  }, [allTasks, selectedTaskIds, taskSearchTerms]);

  const selectedTasks = useMemo(() => {
    const taskById = new Map(allTasks.map((task) => [task.id, task]));
    return selectedTaskIds.map((id) => taskById.get(id)).filter(Boolean);
  }, [allTasks, selectedTaskIds]);

  const addTaskFilter = (task: any) => {
    setSelectedTaskIds((current) => current.includes(task.id) ? current : [...current, task.id]);
    updateFilter({ work_item_id: undefined });
    setTaskFilterSearch("");
    setIsTaskDropdownOpen(true);
  };

  const removeTaskFilter = (taskId: number) => {
    setSelectedTaskIds((current) => current.filter((id) => id !== taskId));
  };

  const clearTaskFilters = () => {
    setSelectedTaskIds([]);
    setTaskFilterSearch("");
    updateFilter({ work_item_id: undefined, work_item_ids: undefined });
    setIsTaskDropdownOpen(false);
  };

  const commitTaskSearchTerm = () => {
    const firstOption = taskOptions[0];
    if (firstOption) {
      addTaskFilter(firstOption);
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

      <div className="activities-filters" ref={activityFilterRef}>
        <div className="filter-row">
          <label className="filter-field filter-field-wide">
            <span className="filter-label">검색</span>
            <input
              className="filter-input"
              value={filters.q ?? ""}
              onChange={(event) => updateFilter({ q: event.target.value || undefined })}
              placeholder="제목, 내용, 태그 검색"
            />
          </label>
          <label className="filter-field">
            <span className="filter-label">작성자</span>
            <select
              className="filter-input"
              value={selectedAuthorValue}
              onChange={(event) => {
                const value = event.target.value;
                updateFilter({
                  author_scope: value === "ME" ? "ME" : "ALL",
                  actor_user_id: value !== ALL && value !== "ME" ? Number(value) : undefined,
                });
              }}
            >
              <option value={ALL}>전체</option>
              <option value="ME">내 활동</option>
              {authorOptions.map((member) => (
                <option key={member.project_member_id} value={member.user_id}>
                  {member.name}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-field">
            <span className="filter-label">유형</span>
            <select className="filter-input" value={filters.category ?? ALL} onChange={(event) => updateFilter({ category: event.target.value })}>
              <option value={ALL}>전체</option>
              <option value="BASIC">내 할일</option>
              <option value="PEER_SUPPORT">팀원 기여</option>
              <option value="COMMON">공통 작업</option>
            </select>
          </label>
          <label className="filter-field">
            <span className="filter-label">검토 상태</span>
            <select className="filter-input" value={filters.review_state ?? ALL} onChange={(event) => updateFilter({ review_state: event.target.value })}>
              <option value={ALL}>전체</option>
              <option value="NORMAL">정상</option>
              <option value="UNDER_REVIEW">검토 중</option>
              <option value="DISPUTED">이의 제기</option>
              <option value="RESOLVED">해결됨</option>
            </select>
          </label>
          <label className="filter-field">
            <span className="filter-label">조건 방식</span>
            <select
              className="filter-input"
              value={filters.filter_operator ?? "AND"}
              onChange={(event) => updateFilter({ filter_operator: event.target.value as "AND" | "OR" })}
            >
              <option value="AND">모든 조건</option>
              <option value="OR">하나라도</option>
            </select>
          </label>
        </div>

        <div className="filter-row filter-row-bottom">
          <label className="filter-field">
            <span className="filter-label">기간</span>
            <select
              className="filter-input"
              value={selectedDatePreset}
              onChange={(event) => {
                const value = event.target.value;
                if (value === ALL) setDatePreset(null);
                if (value === "7") setDatePreset(7);
                if (value === "30") setDatePreset(30);
              }}
            >
              <option value={ALL}>전체</option>
              <option value="7">최근 7일</option>
              <option value="30">최근 30일</option>
            </select>
          </label>
          <label className="filter-field filter-field-wide">
            <span className="filter-label">할일</span>
            <div className="task-combobox">
              {selectedTasks.length > 0 ? (
                <div className="task-filter-chips">
                  {selectedTasks.map((task: any) => (
                    <button
                      key={task.id}
                      type="button"
                      className="task-filter-chip"
                      onClick={() => removeTaskFilter(task.id)}
                      title="클릭하여 제거"
                    >
                      <span>{task.title}</span>
                      <span className="task-filter-chip-x">×</span>
                    </button>
                  ))}
                </div>
              ) : null}
              <input
                className="filter-input"
                value={taskFilterSearch}
                onFocus={() => setIsTaskDropdownOpen(true)}
                onKeyDown={(event) => {
                  if (event.key === "," || event.key === "Enter") {
                    event.preventDefault();
                    commitTaskSearchTerm();
                  }
                  if (event.key === "Backspace" && !taskFilterSearch && selectedTaskIds.length > 0) {
                    setSelectedTaskIds((current) => current.slice(0, -1));
                  }
                }}
                onChange={(event) => {
                  const value = event.target.value;
                  if (value.endsWith(",")) {
                    setTaskFilterSearch(value.slice(0, -1));
                    setIsTaskDropdownOpen(true);
                    setTimeout(commitTaskSearchTerm, 0);
                    return;
                  }
                  setTaskFilterSearch(value);
                  setIsTaskDropdownOpen(true);
                }}
                placeholder={selectedTaskIds.length > 0 ? "다음 할일 검색" : "할일 제목 검색"}
              />
              {taskSearchTerms.length > 1 && selectedTaskIds.length === 0 ? (
                <div className="task-combobox-hint">
                  {taskSearchTerms.length}개 키워드 OR 검색
                </div>
              ) : null}
              {isTaskDropdownOpen && taskFilterSearch.trim() ? (
                <div className="task-combobox-menu">
                  {taskOptions.length > 0 ? (
                    taskOptions.slice(0, 20).map((task) => (
                      <button
                        key={task.id}
                        type="button"
                        className="task-combobox-option"
                        onClick={() => addTaskFilter(task)}
                      >
                        <span className="task-combobox-title">{task.title}</span>
                        {task.assignee?.name ? (
                          <span className="task-combobox-meta">{task.assignee.name}</span>
                        ) : null}
                      </button>
                    ))
                  ) : (
                    <div className="task-combobox-empty">검색 결과가 없습니다.</div>
                  )}
                </div>
              ) : null}
            </div>
          </label>
          <button className="filter-btn reset-filter-btn" onClick={resetFilters}>
            필터 초기화
          </button>
          <span className="activity-count">
            총 {activityTotal}개
          </span> 
        </div>
      </div>

      {/* 피드 리스트 영역 */}
      <div className="activities-list">
        {activityError && <div className="empty-state error-state">{activityError}</div>}
        {isLoadingActivities && activities.length === 0 ? (
          <div className="empty-state">활동 기록을 불러오는 중입니다.</div>
        ) : activities.length === 0 ? (
          <div className="empty-state">해당하는 활동 기록이 없습니다.</div>
        ) : (
          activities.map((activity) => {
            const config = getTypeConfig(activity.activity_category);
            const isMine = activity.actor.id === currentUserId;
            const isModified = activity.is_modified ?? (activity.updated_at && new Date(activity.updated_at) > new Date(activity.occurred_at));
            
            return (
              <div key={activity.id} className="activity-card" style={{ position: 'relative', marginTop: "1rem" }}>
                <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', gap: '5px', zIndex: 10 }}>
                  {isMine && (
                    <>
                      <button onClick={(e) => { e.stopPropagation(); setEditingActivity(activity); }} style={{ fontSize: '0.8rem', padding: '4px 8px', cursor: 'pointer', background: '#f3f4f6', color: '#374151', border: '1px solid #d1d5db', borderRadius: '4px', fontWeight: 'bold' }}>수정</button>
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(activity.id); }} style={{ fontSize: '0.8rem', padding: '4px 8px', cursor: 'pointer', background: '#fee2e2', color: '#dc2626', border: '1px solid #fca5a5', borderRadius: '4px', fontWeight: 'bold' }}>삭제</button>
                    </>
                  )}
                  {activity.activity_category === 'PEER_SUPPORT' && activity.review_state === 'UNDER_REVIEW' && activity.target_user?.id === currentUserId && (
                    <button 
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          await apiJsonRequest(`/api/projects/${project.id}/activities/${activity.id}/approve`, "POST", {});
                          await reloadActivitiesAndOverview();
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
                      {[...activity.work_items].sort((a: any, b: any) => a.id - b.id).map((w: any) => (
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
                    <div className="activity-tags" style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                      {activity.activity_type.split(',').map((t: string) => t.trim()).filter(Boolean).map((t: string) => (
                        <span key={t} style={{ background: '#e0e7ff', color: '#4338ca', padding: '0.2rem 0.5rem', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold' }}>
                          #{t}
                        </span>
                      ))}
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

      {hasMore && (
        <div className="load-more-row">
          <button className="load-more-btn" disabled={isLoadingActivities} onClick={() => void loadActivities({ append: true })}>
            {isLoadingActivities ? "불러오는 중..." : "더 보기"}
          </button>
        </div>
      )}
      
      {isActivityOverlayOpen && (
        <ActivityLogOverlay
          projectId={project.id}
          currentUserId={currentUserId}
          onClose={() => setIsActivityOverlayOpen(false)}
          onSuccess={() => {
            setIsActivityOverlayOpen(false);
            void reloadActivitiesAndOverview();
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
            void reloadActivitiesAndOverview();
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
               const detail = hoveredTask;
               return detail ? (
                 <div style={{ fontSize: '12px', color: '#444' }}>
                   {detail.description && <p style={{ margin: '0 0 8px 0' }}>{detail.description}</p>}
                   <div style={{ background: '#f5f5f5', padding: '6px', borderRadius: '4px' }}>
                     <p style={{ margin: '0 0 4px 0' }}><strong>담당자:</strong> {detail.assignee?.name || '없음'}</p>
                     {(detail.timeline_start_date || detail.timeline_end_date) && (
                       <p style={{ margin: 0 }}><strong>기간:</strong> {detail.timeline_start_date?.split('T')[0] || '?'} ~ {detail.timeline_end_date?.split('T')[0] || '?'}</p>
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
