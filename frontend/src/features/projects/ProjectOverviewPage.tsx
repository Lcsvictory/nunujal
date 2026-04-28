import { ProjectMembersPage } from "./ProjectMembersPage";
import { ProjectTasksPage } from "./ProjectTasksPage";
import { useEffect, useMemo, useState } from "react";
import { ApiError, logout, apiJsonRequest, getApiWebSocketBaseUrl } from "../../lib/api";
import { navigate } from "../../lib/router";
import type { AuthUser } from "../auth/types";
import { fetchProjectDetail, deleteProject } from "./api";
import { ProjectGanttChart } from "./ProjectGanttChart";
import { ProjectEditOverlay } from "./ProjectEditOverlay";
import {
  CollapseIcon,
  ContributionIcon,
  LogoutIcon,
  MembersIcon,
  OverviewIcon,
  TodoIcon,
} from "./ProjectWorkspaceIcons";
import type { ProjectDetail } from "./types";
import {
  formatActivityType,
  formatDateRange,
  formatDateTime,
  formatJoinPolicy,
  formatProjectStatus,
  formatReviewState,
} from "./utils";

type ProjectOverviewPageProps = {
  projectId: number | null;
  onMoveToProjects: () => void;
};

type WorkspaceSection = "overview" | "tasks" | "activities" | "members" | "contribution" | "profile";

type WorkspaceNavigationItem = {
  key: Exclude<WorkspaceSection, "profile">;
  label: string;
  icon: (props: { className?: string }) => JSX.Element;
};

const navigationItems: WorkspaceNavigationItem[] = [
  { key: "overview", label: "개요", icon: OverviewIcon },
  { key: "tasks", label: "할일", icon: TodoIcon },
  { key: "activities", label: "활동", icon: ContributionIcon },
  { key: "members", label: "팀원", icon: MembersIcon },
  { key: "contribution", label: "기여도", icon: ContributionIcon },
];

function buildInitials(name: string | undefined): string {
  if (!name) {
    return "N";
  }

  return name.slice(0, 1).toUpperCase();
}

import { ProjectActivitiesPage } from "./ProjectActivitiesPage";

export function ProjectOverviewPage({
  projectId,
  onMoveToProjects,
}: ProjectOverviewPageProps) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>("overview");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isEditProjectOpen, setIsEditProjectOpen] = useState(false);

  // ========== 프로젝트 웹소켓 현재 접속자 상태 관리 ==========
  const [activeUsers, setActiveUsers] = useState<any[]>([]);

  useEffect(() => {
    if (!projectId) return;

    const wsUrl = `${getApiWebSocketBaseUrl()}/api/projects/${projectId}/presence/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "presence_update") {
          setActiveUsers(data.active_users || []);
        }
      } catch (err) {
        console.error("Failed to parse presence update", err);
      }
    };

    socket.onclose = () => {
      console.log("Presence WebSocket closed");
    };

    return () => {
      socket.close();
    };
  }, [projectId]);

  // team members excluding myself
  const currentUserId = currentUser?.id;
  const activeTeammates = activeUsers.filter(u => u.id !== currentUserId);


  const currentSection = activeSection;

  const loadProject = async () => {
    if (projectId === null) {
      setProject(null);
      setCurrentUser(null);
      setIsLoading(false);
      setErrorMessage("프로젝트 식별자가 없습니다.");
      return;
    }

    setErrorMessage(null);

    try {
      const response = await fetchProjectDetail(projectId);
      setProject(response.project);
      setCurrentUser(response.current_user);
    } catch (error) {
      setProject(null);
      setCurrentUser(null);
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : "프로젝트 개요를 불러오지 못했습니다.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setActiveSection("overview");
  }, [projectId]);

  useEffect(() => {
    void loadProject();
  }, [projectId]);

  const completionRate = project?.overview.completion_rate ?? 0;

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
    } catch {
      // If the logout request fails, move the user to login anyway.
    } finally {
      setIsLoggingOut(false);
      navigate("/login");
    }
  };

  const handleDeleteProject = async () => {
    if (!project) return;
    if (!window.confirm(`정말 "${project.title}" 프로젝트를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`)) {
      return;
    }

    try {
      await deleteProject(project.id);
      onMoveToProjects();
    } catch (error) {
      alert("프로젝트를 삭제하는 데 실패했습니다.");
    }
  };

  const renderOverviewSection = () => {
    if (!project) {
      return null;
    }

    return (
      <div className="workspace-section-stack">
        <ProjectGanttChart
          projectId={project.id}
          startDate={project.start_date}
          endDate={project.end_date}
          projectMembers={project.members}
          isVisible={currentSection === "overview"}
        />

        <section className="surface-panel workspace-project-card">
          <div className="workspace-project-card-top">
            <div className="workspace-project-copy">
              <div className="workspace-title-row">
                <h1>{project.title}</h1>
                <span className="status-pill">{formatProjectStatus(project.status)}</span>
              </div>
              <p>{project.description || "프로젝트 설명이 아직 입력되지 않았습니다."}</p>
            </div>

            {project.my_membership.project_role === "LEADER" && (
              <div style={{ display: "flex", gap: "8px" }}>
                <button 
                  type="button" 
                  className="button button-primary workspace-inline-button"
                  onClick={() => setIsEditProjectOpen(true)}
                >
                  수정
                </button>
                <button 
                  type="button" 
                  className="button button-ghost workspace-inline-button"
                  onClick={handleDeleteProject}
                  style={{ color: "var(--status-danger)" }}
                >
                  삭제
                </button>
              </div>
            )}
          </div>

          <div className="workspace-summary-text" style={{ padding: "0 24px 24px 24px", display: "flex", flexDirection: "column", gap: "12px", fontSize: "1rem", lineHeight: "1.6" }}>
            <p>
              프로젝트 기간 : <strong>{formatDateRange(project.start_date, project.end_date)}</strong> <br/>
              <strong>총 {project.member_count}명</strong>(내 직책: {project.my_membership.position_label})<br/> 
            </p>
            <div style={{ padding: "12px 16px", background: "var(--background-modifier-hover, rgba(0,0,0,0.05))", borderRadius: "8px", borderLeft: "4px solid var(--color-primary, #0066ff)", display: "inline-block", alignSelf: "flex-start" }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted, #666)" }}>참여 코드 (정책: {formatJoinPolicy(project.join_policy)})</span><br/>
              <strong style={{ fontSize: "1.25rem", letterSpacing: "1px", color: "var(--color-primary, #0066ff)" }}>{project.join_code}</strong>
            </div>
          </div>
        </section>

        <div className="workspace-overview-grid">
          <section className="surface-panel workspace-progress-panel">
            <div className="section-heading">
              <div>
                {/* <p className="section-label">진행률</p> */}
                <h2>전체 진행률</h2>
              </div>
              <strong>{completionRate}%</strong>
            </div>

            <div className="progress-track" aria-hidden="true">
              <div className="progress-fill" style={{ width: `${completionRate}%` }} />
            </div>
            
            &nbsp;
            <div className="progress-breakdown">
              <div>
                <span>할일</span>
                <strong>{project.overview.todo_work_items}</strong>
              </div>
              <div>
                <span>진행 중</span>
                <strong>{project.overview.in_progress_work_items}</strong>
              </div>
              <div>
                <span>완료</span>
                <strong>{project.overview.done_work_items}</strong>
              </div>
            </div>
          </section>

          <section className="surface-panel workspace-activity-panel">
            <div className="section-heading">
              <div>
                {/* <p className="section-label">활동</p> */}
                <h2>최근 활동</h2>
                &nbsp;
              </div>
            </div>

            {project.overview.recent_activities.length > 0 ? (
              <div className="activity-list">
                {project.overview.recent_activities.map((activity) => (
                  <article key={activity.id} className="activity-item">
                    <div className="activity-copy">
                      <div className="activity-topline">
                        <strong>{activity.title}</strong>
                        <span className="meta-chip">
                          {formatReviewState(activity.review_state)}
                        </span>
                        {activity.activity_category === 'PEER_SUPPORT' && 
                         activity.review_state === 'UNDER_REVIEW' && 
                         activity.target_user?.id === currentUserId && (
                          <button 
                            type="button" 
                            style={{ padding: "2px 8px", fontSize: "12px", background: "#10b981", color: "white", borderRadius: "4px", border: "none", cursor: "pointer", marginLeft: "10px" }}
                            onClick={async () => {
                              try {
                                await apiJsonRequest(`/api/projects/${project.id}/activities/${activity.id}/approve`, "POST", {});
                                loadProject();
                              } catch (e) {
                                alert("승인 처리 중 오류가 발생했습니다.");
                              }
                            }}
                          >
                            ✓ 승인하기
                          </button>
                        )}
                      </div>
                      <p>{activity.content}</p>
                      <div className="activity-meta">
                        <span style={{ fontWeight: 'bold' }}>{activity.actor.name}</span>
                        {activity.activity_category === 'PEER_SUPPORT' && activity.target_user && (
                            <span>➔ <strong style={{ color: '#0066ff' }}>{activity.target_user.name}</strong> 지원</span>
                        )}
                        <span>{formatActivityType(activity.activity_type)}</span>
                        <span>{formatDateTime(activity.occurred_at)}</span>
                        {activity.updated_at && new Date(activity.updated_at) > new Date(activity.occurred_at) && (
                          <span style={{ fontSize: '0.8rem', color: '#666', fontStyle: 'italic' }}>(수정됨)</span>
                        )}
                        <span>{(activity.work_items && activity.work_items.length > 0) ? `[${activity.work_items.map(w => w.title).join(', ')}]` : "연결된 업무 없음"}</span>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-copy">아직 기록된 활동이 없습니다.</p>
            )}
          </section>
        </div>
      </div>
    );
  };

  const renderPlaceholderSection = () => {
    const sectionTitleMap: Record<Exclude<WorkspaceSection, "overview">, string> = {
      tasks: "할일 페이지",
      activities: "활동 피드 페이지",
      members: "팀원 페이지",
      contribution: "기여도 페이지",
      profile: "내 정보 페이지",
    };

    const title = sectionTitleMap[activeSection as Exclude<WorkspaceSection, "overview">];
    
    if (activeSection === "members" && project) {
      return <ProjectMembersPage project={project} />;
    }

    if (activeSection === "tasks" && project) {
      return <ProjectTasksPage project={project} onRefresh={loadProject} />;
    }

    if (activeSection === "activities") {
      return project ? <ProjectActivitiesPage project={project} onRefresh={loadProject} /> : null;
    }

    return (
      <section className="surface-panel workspace-placeholder-panel">
        <p className="section-label">prototype</p>
        <h1>{title}</h1>
        <p>
          이번 단계에서는 프로젝트 내부 레이아웃과 간트차트 프로토타입을 먼저
          확인할 수 있도록 구성했습니다. 이 섹션은 다음 피드백 이후 구체화하면
          됩니다.
        </p>
      </section>
    );
  };

  return (
    <div className="workspace-shell">
      <header className="workspace-topbar">
        <div className="workspace-brand">
          <div className="workspace-brand-mark">N</div>
          <div className="workspace-brand-copy">
            <strong>누누잘</strong>
            <span>기여도 분석 플랫폼</span>
          </div>
        </div>

        <div className="workspace-topbar-actions" style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <div className="workspace-active-users" style={{ display: "flex", gap: "8px", marginRight: "10px" }}>
            {activeTeammates.map((u, idx) => (
              <div 
                key={idx} 
                className="workspace-active-user-avatar"
                style={{ 
                  position: "relative",
                  width: "44px", 
                  height: "44px", 
                  borderRadius: "50%", 
                  border: "2px solid white", 
                  marginLeft: "-10px", 
                  zIndex: activeTeammates.length - idx, 
                  backgroundColor: "#ccc", 
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "center", 
                  fontSize: "18px", 
                  fontWeight: "bold", 
                  color: "#555" 
                }} 
              >
                {u.profile_image_url ? (
                  <img 
                    src={u.profile_image_url} 
                    alt={u.name} 
                    style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} 
                  />
                ) : (
                  buildInitials(u.name)
                )}
                <div className="active-user-tooltip">
                  {u.name}
                </div>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="workspace-profile-trigger"
            onClick={() => setActiveSection("profile")}
          >
            {currentUser?.profile_image_url ? (
              <img
                className="workspace-profile-image"
                src={currentUser.profile_image_url}
                alt={`${currentUser.name} 프로필`}
              />
            ) : (
              <div className="workspace-profile-fallback">{buildInitials(currentUser?.name)}</div>
            )}

            <div className="workspace-profile-copy">
              <strong>{currentUser?.name ?? "사용자"}</strong>
              
            </div>
          </button>
        </div>
      </header>

      <div className={`workspace-layout ${isSidebarCollapsed ? "workspace-layout-collapsed" : ""}`}>
        <aside
          className={`workspace-sidebar ${isSidebarCollapsed ? "workspace-sidebar-collapsed" : ""}`}
        >
          <div className="workspace-sidebar-header">
            <button
              type="button"
              className="workspace-sidebar-toggle"
              onClick={() => setIsSidebarCollapsed((current) => !current)}
              aria-label={isSidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기"}
            >
              <CollapseIcon
                className={`workspace-inline-icon ${isSidebarCollapsed ? "workspace-inline-icon-rotated" : ""}`}
              />
              {!isSidebarCollapsed ? <span>메뉴 접기</span> : null}
            </button>
          </div>

          <nav className="workspace-nav">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentSection === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  className={`workspace-nav-item ${isActive ? "workspace-nav-item-active" : ""}`}
                  onClick={() => setActiveSection(item.key)}
                  title={isSidebarCollapsed ? item.label : undefined}
                  aria-current={isActive ? "page" : undefined}
                >
                  <Icon className="workspace-nav-icon" />
                  {!isSidebarCollapsed ? <span>{item.label}</span> : null}
                </button>
              );
            })}
          </nav>

          <div className="workspace-sidebar-footer">
            <button
              type="button"
              className="workspace-sidebar-logout"
              onClick={onMoveToProjects}
              title={isSidebarCollapsed ? "프로젝트 목록으로" : undefined}
              style={{ marginBottom: "5px" }}
            >
              <OverviewIcon className="workspace-nav-icon" />
              {!isSidebarCollapsed ? <span>프로젝트 목록으로</span> : null}
            </button>
            <button
              type="button"
              className="workspace-sidebar-logout"
              onClick={() => void handleLogout()}
              disabled={isLoggingOut}
              title={isSidebarCollapsed ? "로그아웃" : undefined}
            >
              <LogoutIcon className="workspace-nav-icon" />
              {!isSidebarCollapsed ? <span>{isLoggingOut ? "로그아웃 중..." : "로그아웃"}</span> : null}
            </button>
          </div>
        </aside>

        <main className="workspace-content">
          {isLoading ? (
            <section className="surface-panel overview-loading">
              <div className="skeleton-line skeleton-line-short" />
              <div className="skeleton-line" />
              <div className="skeleton-line" />
            </section>
          ) : null}

          {!isLoading && errorMessage ? (
            <section className="surface-panel empty-panel">
              <h1>개요 화면을 불러오지 못했습니다</h1>
              <p>{errorMessage}</p>
            </section>
          ) : null}

          {!isLoading && !errorMessage ? (
            <>
              <div
                className={
                  activeSection === "overview"
                    ? "workspace-section-visible"
                    : "workspace-section-hidden"
                }
                aria-hidden={activeSection !== "overview"}
              >
                {renderOverviewSection()}
              </div>

              <div
                className={
                  activeSection === "overview"
                    ? "workspace-section-hidden"
                    : "workspace-section-visible"
                }
                aria-hidden={activeSection === "overview"}
              >
                {activeSection === "overview" ? null : renderPlaceholderSection()}
              </div>
            </>
          ) : null}
        </main>
      </div>

      <ProjectEditOverlay
        open={isEditProjectOpen}
        project={project}
        onClose={() => setIsEditProjectOpen(false)}
        onUpdated={loadProject}
      />
    </div>
  );
}
