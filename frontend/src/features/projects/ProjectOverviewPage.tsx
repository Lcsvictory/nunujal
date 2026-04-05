import { useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { fetchProjectDetail } from "./api";
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

export function ProjectOverviewPage({
  projectId,
  onMoveToProjects,
}: ProjectOverviewPageProps) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (projectId === null) {
      setProject(null);
      setIsLoading(false);
      setErrorMessage("프로젝트 식별자가 없습니다.");
      return;
    }

    let isMounted = true;

    const loadProject = async () => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const response = await fetchProjectDetail(projectId);
        if (!isMounted) {
          return;
        }
        setProject(response.project);
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setProject(null);
        setErrorMessage(
          error instanceof ApiError
            ? error.message
            : "프로젝트 개요를 불러오지 못했습니다.",
        );
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void loadProject();

    return () => {
      isMounted = false;
    };
  }, [projectId]);

  const completionRate = project?.overview.completion_rate ?? 0;

  return (
    <div className="overview-shell">
      <button type="button" className="button button-ghost button-inline" onClick={onMoveToProjects}>
        ← 프로젝트 목록으로
      </button>

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

      {!isLoading && project ? (
        <>
          <section className="surface-panel overview-hero">
            <div className="overview-hero-copy">
              <span className="hero-badge">overview</span>
              <div className="overview-title-row">
                <h1>{project.title}</h1>
                <span className="status-pill">{formatProjectStatus(project.status)}</span>
              </div>
              <p>{project.description || "프로젝트 설명이 아직 입력되지 않았습니다."}</p>
            </div>

            <dl className="overview-hero-meta">
              <div>
                <dt>프로젝트 기간</dt>
                <dd>{formatDateRange(project.start_date, project.end_date)}</dd>
              </div>
              <div>
                <dt>내 역할</dt>
                <dd>{project.my_membership.position_label}</dd>
              </div>
              <div>
                <dt>참여 정책</dt>
                <dd>{formatJoinPolicy(project.join_policy)}</dd>
              </div>
            </dl>
          </section>

          <section className="overview-metric-grid">
            <article className="surface-panel metric-card">
              <span>전체 진행률</span>
              <strong>{completionRate}%</strong>
              <p>완료된 업무 비율을 기준으로 계산했습니다.</p>
            </article>
            <article className="surface-panel metric-card">
              <span>총 업무 수</span>
              <strong>{project.overview.total_work_items}</strong>
              <p>개요 화면 단계에서는 업무 요약만 노출합니다.</p>
            </article>
            <article className="surface-panel metric-card">
              <span>프로젝트 인원</span>
              <strong>{project.member_count}명</strong>
              <p>활성 멤버만 집계합니다.</p>
            </article>
            <article className="surface-panel metric-card">
              <span>참여 코드</span>
              <strong>{project.join_code}</strong>
              <p>{project.join_code_active ? "현재 사용 가능" : "비활성 상태"}</p>
            </article>
          </section>

          <div className="overview-grid">
            <section className="surface-panel overview-progress-card">
              <div className="section-heading">
                <div>
                  <p className="section-label">progress</p>
                  <h2>업무 진행 요약</h2>
                </div>
                <strong>{completionRate}%</strong>
              </div>

              <div className="progress-track" aria-hidden="true">
                <div
                  className="progress-fill"
                  style={{ width: `${completionRate}%` }}
                />
              </div>

              <div className="progress-breakdown">
                <div>
                  <span>할 일</span>
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

            <section className="surface-panel overview-join-card">
              <div className="section-heading">
                <div>
                  <p className="section-label">invite</p>
                  <h2>참여 코드 상태</h2>
                </div>
              </div>

              <div className="invite-code-box">{project.join_code}</div>
              <p className="invite-copy">
                {project.join_code_active
                  ? "현재 참여 코드는 활성 상태입니다."
                  : "현재 참여 코드는 비활성 상태입니다."}
              </p>
              <p className="invite-copy">
                만료 시각:{" "}
                {project.join_code_expires_at
                  ? formatDateTime(project.join_code_expires_at)
                  : "설정 없음"}
              </p>
            </section>

            <section className="surface-panel overview-members-card">
              <div className="section-heading">
                <div>
                  <p className="section-label">members</p>
                  <h2>프로젝트 멤버</h2>
                </div>
              </div>

              <div className="member-list">
                {project.members.map((member) => (
                  <article key={member.project_member_id} className="member-item">
                    <div className="member-avatar" aria-hidden="true">
                      {member.name.slice(0, 1)}
                    </div>
                    <div className="member-copy">
                      <strong>{member.name}</strong>
                      <span>{member.position_label}</span>
                    </div>
                    <span className="meta-chip">{member.project_role}</span>
                  </article>
                ))}
              </div>
            </section>

            <section className="surface-panel overview-activity-card">
              <div className="section-heading">
                <div>
                  <p className="section-label">activity</p>
                  <h2>최근 활동</h2>
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
                        </div>
                        <p>{activity.content}</p>
                        <div className="activity-meta">
                          <span>{activity.actor.name}</span>
                          <span>{formatActivityType(activity.activity_type)}</span>
                          <span>{formatDateTime(activity.occurred_at)}</span>
                          <span>{activity.work_item?.title ?? "연결된 업무 없음"}</span>
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
        </>
      ) : null}
    </div>
  );
}
