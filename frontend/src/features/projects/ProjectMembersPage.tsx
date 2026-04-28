import { useEffect, useState, useMemo } from "react";
import { ProjectDetail, ProjectMemberSummary, ProjectWorkItemSummary } from "./types";
import { fetchProjectMembers, fetchProjectJoinRequests, reviewProjectJoinRequest, fetchProjectWorkItems } from "./api";

type ProjectMembersPageProps = {
  project: ProjectDetail;
};

type MemberStats = {
  total: number;
  inProgress: number;
  done: number;
};

export function ProjectMembersPage({ project }: ProjectMembersPageProps) {
  const [members, setMembers] = useState<ProjectMemberSummary[]>([]);
  const [requests, setRequests] = useState<any[]>([]);
  const [workItems, setWorkItems] = useState<ProjectWorkItemSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isLeader = project.my_membership.project_role === "LEADER";

  async function loadData() {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const [membersRes, requestsRes, workItemsRes] = await Promise.all([
        fetchProjectMembers(project.id),
        isLeader ? fetchProjectJoinRequests(project.id) : Promise.resolve({ items: [] }),
        fetchProjectWorkItems(project.id),
      ]);
      setMembers(membersRes.items);
      setWorkItems(workItemsRes.items);
      if (isLeader) {
        setRequests(requestsRes.items);
      }
    } catch (e: any) {
      setErrorMessage(e.message || "데이터를 불러오는데 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, [project.id, isLeader]);

  async function handleReview(requestId: number, status: "APPROVED" | "REJECTED") {
    if (!confirm(`정말로 이 요청을 ${status === "APPROVED" ? "승인" : "거절"} 하시겠습니까?`)) {
      return;
    }
    try {
      await reviewProjectJoinRequest(project.id, requestId, { request_status: status });
      await loadData();
    } catch (e: any) {
      alert(e.message || "요청을 처리하는데 실패했습니다.");
    }
  }

  const memberStats = useMemo(() => {
    const stats: Record<number, MemberStats> = {};
    for (const member of members) {
      stats[member.user_id] = { total: 0, inProgress: 0, done: 0 };
    }

    for (const item of workItems) {
      if (item.assignee) {
        const pId = item.assignee.id;
        if (!stats[pId]) continue;
        stats[pId].total += 1;
        if (item.status === "DONE") {
          stats[pId].done += 1;
        } else if (item.status === "IN_PROGRESS") {
          stats[pId].inProgress += 1;
        }
      }
    }
    return stats;
  }, [members, workItems]);

  if (isLoading) {
    return (
      <section className="surface-panel overview-loading">
        <div className="skeleton-line skeleton-line-short" />
        <div className="skeleton-line" />
        <div className="skeleton-line" />
      </section>
    );
  }

  return (
    <section className="surface-panel" style={{ padding: "2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2rem" }}>
        <h2>팀원 현황</h2>
      </div>

      {errorMessage && <div className="error-message" style={{ color: "red", marginBottom: "1rem" }}>{errorMessage}</div>}

      <div className="workspace-summary-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px", marginBottom: "3rem" }}>
        {members.map(m => {
          const stats = memberStats[m.user_id] || { total: 0, inProgress: 0, done: 0 };
          return (
            <article key={m.project_member_id} className="workspace-summary-item" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                {m.profile_image_url ? (
                  <img src={m.profile_image_url} alt={m.name} style={{ width: "48px", height: "48px", borderRadius: "50%", objectFit: "cover", border: "1px solid var(--border-color, #e5e7eb)" }} />
                ) : (
                  <div style={{ width: "48px", height: "48px", borderRadius: "50%", background: "var(--color-primary-light, #e0e7ff)", color: "var(--color-primary, #0066ff)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "1.2rem" }}>
                    {m.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div>
                  <div style={{ fontWeight: "bold", fontSize: "1.1rem" }}>{m.name}</div>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted, #666)" }}>{m.email}</div>
                </div>
              </div>
              <div style={{ marginTop: "4px" }}>
                <span className="status-pill" style={{ background: m.project_role === 'LEADER' ? '#fef3c7' : '#f3f4f6', color: m.project_role === 'LEADER' ? '#b45309' : '#4b5563' }}>
                  {m.project_role === 'LEADER' ? "팀장" : "팀원"} · {m.position_label}
                </span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", marginTop: "8px", textAlign: "center", background: "var(--background-modifier-hover, rgba(0,0,0,0.03))", padding: "12px", borderRadius: "8px" }}>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #666)", marginBottom: "4px" }}>할일</div>
                  <strong style={{ fontSize: "1.1rem", color: "var(--text-primary, #111)" }}>{stats.total}</strong>
                </div>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #666)", marginBottom: "4px" }}>진행</div>
                  <strong style={{ fontSize: "1.1rem", color: "var(--color-primary, #0066ff)" }}>{stats.inProgress}</strong>
                </div>
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #666)", marginBottom: "4px" }}>완료</div>
                  <strong style={{ fontSize: "1.1rem", color: "var(--status-success, #10b981)" }}>{stats.done}</strong>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {isLeader && (
        <div style={{ marginTop: "40px" }}>
          <h2>참여 요청 ({requests.length}건)</h2>
          <div style={{ marginTop: "1rem" }}>
            {requests.length === 0 ? (
              <p style={{ color: "var(--text-muted, #666)", background: "var(--background-modifier-hover, rgba(0,0,0,0.02))", padding: "2rem", textAlign: "center", borderRadius: "8px" }}>
                대기 중인 참여 요청이 없습니다.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {requests.map(r => (
                  <article key={r.id} className="surface-panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", border: "1px solid var(--border-color, #e5e7eb)", boxShadow: "none" }}>
                    <div>
                      <div style={{ marginBottom: "4px", fontSize: "1.05rem" }}>
                        <strong>{r.requester_name}</strong> <span style={{ color: "var(--text-muted, #666)", fontSize: "0.9rem" }}>({r.requester_email})</span>
                      </div>
                      {r.request_message && (
                        <div style={{ fontSize: "0.95rem", marginBottom: "4px" }}>
                          메시지: {r.request_message}
                        </div>
                      )}
                      {r.requested_position_label && (
                        <div style={{ fontSize: "0.85rem", color: "var(--color-primary, #0066ff)", background: "var(--color-primary-light, #e0e7ff)", padding: "2px 8px", borderRadius: "12px", display: "inline-block" }}>
                          희망 직책: {r.requested_position_label}
                        </div>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button 
                        onClick={() => handleReview(r.id, "APPROVED")}
                        className="button button-primary"
                        style={{ minWidth: "70px" }}
                      >
                        승인
                      </button>
                      <button 
                        onClick={() => handleReview(r.id, "REJECTED")}
                        className="button button-ghost"
                        style={{ minWidth: "70px", color: "var(--status-danger, #ef4444)" }}
                      >
                        거절
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
