import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { ApiError, logout } from "../../lib/api";
import type { AuthUser } from "../auth/types";
import { fetchProjects, deleteProject } from "./api";
import { ProjectCreateOverlay } from "./ProjectCreateOverlay";
import { ProjectJoinOverlay } from "./ProjectJoinOverlay";
import type { JoinProjectResponse, ProjectSummary } from "./types";
import { formatDateRange, formatJoinPolicy, formatProjectStatus } from "./utils";
import { LogoutIcon } from "./ProjectWorkspaceIcons";

type Notice = {
  tone: "success" | "error";
  message: string;
} | null;

type FilterType = "ALL" | "IN_PROGRESS" | "LEADER";

type ProjectsPageProps = {
  onMoveToLogin: () => void;
  onOpenProject: (projectId: number) => void;
};

export function ProjectsPage({
  onMoveToLogin,
  onOpenProject,
}: ProjectsPageProps) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [requiresLogin, setRequiresLogin] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<FilterType>("ALL");
  const [notice, setNotice] = useState<Notice>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isJoinOpen, setIsJoinOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; project: ProjectSummary } | null>(null);

  const loadProjects = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    setRequiresLogin(false);

    try {
      const response = await fetchProjects();
      setProjects(response.projects ?? []);
      setCurrentUser(response.current_user ?? response.user ?? null);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setRequiresLogin(true);
        setProjects([]);
        setCurrentUser(null);
        setErrorMessage("로그인이 필요합니다.");
      } else {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "프로젝트 목록을 불러오지 못했습니다.",
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadProjects();
  }, []);

  const filteredProjects = useMemo(() => {
    let result = projects;

    if (filterType === "IN_PROGRESS") {
      result = result.filter((project) => project.status === "IN_PROGRESS");
    } else if (filterType === "LEADER") {
      result = result.filter((project) => project.my_membership.project_role === "LEADER");
    }

    const keyword = searchTerm.trim().toLowerCase();
    if (!keyword) {
      return result;
    }

    return result.filter((project) => {
      const title = project.title.toLowerCase();
      const description = project.description.toLowerCase();
      return title.includes(keyword) || description.includes(keyword);
    });
  }, [projects, searchTerm, filterType]);

  const projectStats = useMemo(() => {
    return {
      total: projects.length,
      planning: projects.filter((project) => project.status === "PLANNING").length,
      inProgress: projects.filter((project) => project.status === "IN_PROGRESS").length,
      done: projects.filter((project) => project.status === "DONE").length,
      leader: projects.filter((project) => project.my_membership.project_role === "LEADER").length,
    };
  }, [projects]);

  const handleCreated = async (projectId: number, message: string) => {
    setNotice({ tone: "success", message });
    await loadProjects();
    onOpenProject(projectId);
  };

  const handleJoined = async (result: JoinProjectResponse) => {
    setNotice({
      tone: result.membership_created ? "success" : "success",
      message: result.message,
    });
    await loadProjects();
    if (result.membership_created) {
      onOpenProject(result.project.id);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      // If the logout request fails, move the user to login anyway.
    } finally {
      onMoveToLogin();
    }
  };

  const handleContextMenu = (e: MouseEvent, project: ProjectSummary) => {
    e.preventDefault();
    setContextMenu({ x: e.pageX, y: e.pageY, project });
  };

  const handleDeleteProject = async (project: ProjectSummary) => {
    setContextMenu(null);
    if (project.my_membership.project_role !== "LEADER") {
      alert("팀장만 프로젝트를 삭제할 수 있습니다.");
      return;
    }
    if (!window.confirm(`정말 "${project.title}" 프로젝트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) {
      return;
    }
    
    try {
      await deleteProject(project.id);
      setNotice({ tone: "success", message: "프로젝트가 삭제되었습니다." });
      await loadProjects();
    } catch (error) {
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "프로젝트 삭제 실패",
      });
    }
  };

  const closeContextMenu = () => {
    if (contextMenu) setContextMenu(null);
  };

  return (
    <div onClick={closeContextMenu}>
      <ProjectCreateOverlay
        open={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={handleCreated}
      />
      <ProjectJoinOverlay
        open={isJoinOpen}
        onClose={() => setIsJoinOpen(false)}
        onJoined={handleJoined}
      />

      <div className="projects-shell">
        <section className="surface-panel projects-hero">
          <div className="projects-hero-copy">
            <span className="hero-badge">projects</span>
            <h1>프로젝트 선택</h1>
            <p>&nbsp;</p>
          </div>

          <div className="projects-hero-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={handleLogout}
              style={{ whiteSpace: "nowrap", gap: "8px", display: "inline-flex", alignItems: "center" }}
            >
              로그아웃
              {/* <LogoutIcon />  */}
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setIsJoinOpen(true)}
            >
              프로젝트 참여
            </button>
            <button
              type="button"
              className="button button-primary"
              onClick={() => setIsCreateOpen(true)}
            >
              프로젝트 생성
            </button>
          </div>
        </section>

        {notice ? (
          <div
            className={`surface-banner ${notice.tone === "error" ? "surface-banner-error" : ""}`}
          >
            {notice.message}
          </div>
        ) : null}

        <div className="projects-layout">
          <section className="projects-main">
            <div className="surface-panel projects-toolbar">
              <label className="search-field">
                <span className="search-label">검색</span>
                <input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="프로젝트 이름 또는 설명 검색"
                />
              </label>

              <div className="toolbar-pills">
                <button
                  type="button"
                  className={`meta-chip ${filterType === "ALL" ? "active" : ""}`}
                  onClick={() => setFilterType("ALL")}
                  style={{ cursor: "pointer", border: "none", background: filterType === "ALL" ? "rgba(124, 143, 191, 0.2)" : "var(--surface-color-2)" }}
                >
                  전체 {projectStats.total}
                </button>
                <button
                  type="button"
                  className={`meta-chip ${filterType === "IN_PROGRESS" ? "active" : ""}`}
                  onClick={() => setFilterType("IN_PROGRESS")}
                  style={{ cursor: "pointer", border: "none", background: filterType === "IN_PROGRESS" ? "rgba(124, 143, 191, 0.2)" : "var(--surface-color-2)" }}
                >
                  진행 중 {projectStats.inProgress}
                </button>
                <button
                  type="button"
                  className={`meta-chip ${filterType === "LEADER" ? "active" : ""}`}
                  onClick={() => setFilterType("LEADER")}
                  style={{ cursor: "pointer", border: "none", background: filterType === "LEADER" ? "rgba(124, 143, 191, 0.2)" : "var(--surface-color-2)" }}
                >
                  내가 팀장 {projectStats.leader}
                </button>
              </div>
            </div>

            {isLoading ? (
              <div className="projects-grid">
                {[0, 1, 2].map((index) => (
                  <article key={index} className="project-card project-card-skeleton">
                    <div className="skeleton-line skeleton-line-short" />
                    <div className="skeleton-line" />
                    <div className="skeleton-line" />
                    <div className="skeleton-line skeleton-line-short" />
                  </article>
                ))}
              </div>
            ) : null}

            {!isLoading && requiresLogin ? (
              <section className="surface-panel empty-panel">
                <h2>로그인이 필요합니다</h2>
                <button type="button" className="button button-primary" onClick={onMoveToLogin}>
                  로그인 화면으로 이동
                </button>
              </section>
            ) : null}

            {!isLoading && !requiresLogin && errorMessage ? (
              <section className="surface-panel empty-panel">
                <h2>프로젝트를 불러오지 못했습니다</h2>
                <p>{errorMessage}</p>
                <button type="button" className="button button-secondary" onClick={() => void loadProjects()}>
                  다시 시도
                </button>
              </section>
            ) : null}

            {!isLoading && !requiresLogin && !errorMessage ? (
              filteredProjects.length > 0 ? (
                <div className="projects-grid">
                  {filteredProjects.map((project) => (
                    <button
                      key={project.id}
                      type="button"
                      className="project-card"
                      onClick={() => onOpenProject(project.id)}
                      onContextMenu={(e) => handleContextMenu(e, project)}
                    >
                      <div className="project-card-top">
                        <span className="status-pill">
                          {formatProjectStatus(project.status)}
                        </span>
                        <span className="meta-chip">{formatJoinPolicy(project.join_policy)}</span>
                      </div>

                      <h3>{project.title}</h3>
                      <p>
                        {project.description || "프로젝트 설명이 아직 입력되지 않았습니다."}
                      </p>

                      <dl className="project-card-facts">
                        <div>
                          <dt>기간</dt>
                          <dd>{formatDateRange(project.start_date, project.end_date)}</dd>
                        </div>
                        <div>
                          <dt>내 역할</dt>
                          <dd>{project.my_membership.position_label}</dd>
                        </div>
                        <div>
                          <dt>프로젝트 역할</dt>
                          <dd>{project.my_membership.project_role}</dd>
                        </div>
                        <div>
                          <dt>참여 인원</dt>
                          <dd>{project.member_count}명</dd>
                        </div>
                      </dl>
                    </button>
                  ))}
                </div>
              ) : (
                <section className="surface-panel empty-panel">
                  <h2>보이는 프로젝트가 없습니다</h2>
                  <p>
                    새 프로젝트를 만들거나 참여 코드를 입력해 프로젝트에 합류하세요.
                  </p>
                </section>
              )
            ) : null}
          </section>

          <aside className="projects-sidebar">
            <section className="surface-panel side-panel">
              <p className="side-panel-label">현재 사용자</p>
              <strong>{currentUser?.name ?? "로그인 정보 없음"}</strong>
              <span>{currentUser?.email ?? "프로젝트 화면 접근 시 확인됩니다."}</span>
              <span>
                {currentUser
                  ? `${currentUser.provider} · ${currentUser.status}`
                  : "로그인 이후 사용자 요약이 표시됩니다."}
              </span>
            </section>

            <section className="surface-panel side-panel">
              <p className="side-panel-label">프로젝트 현황</p>
              <div className="side-stat-grid">
                <div>
                  <strong>{projectStats.total}</strong>
                  <span>전체</span>
                </div>
                <div>
                  <strong>{projectStats.planning}</strong>
                  <span>계획 중</span>
                </div>
                <div>
                  <strong>{projectStats.inProgress}</strong>
                  <span>진행 중</span>
                </div>
                <div>
                  <strong>{projectStats.done}</strong>
                  <span>완료</span>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
      
      {contextMenu && (
        <div
          style={{
            position: "absolute",
            top: contextMenu.y,
            left: contextMenu.x,
            backgroundColor: "var(--surface-color-2)",
            border: "1px solid var(--border-color)",
            padding: "8px",
            borderRadius: "var(--radius-md)",
            boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
            zIndex: 1000,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="button button-secondary"
            style={{  display: "block", width: "100%", textAlign: "left", padding: "8px 12px" }}
            onClick={(e) => {
              e.stopPropagation();
              handleDeleteProject(contextMenu.project);
            }}
          >
            ❌ 프로젝트 삭제
          </button>
        </div>
      )}
    </div>
  );
}
