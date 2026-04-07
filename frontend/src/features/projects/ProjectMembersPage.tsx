import { useEffect, useState } from "react";
import { ProjectDetail, ProjectMemberSummary } from "./types";
import { fetchProjectMembers, fetchProjectJoinRequests, reviewProjectJoinRequest } from "./api";

type ProjectMembersPageProps = {
  project: ProjectDetail;
};

export function ProjectMembersPage({ project }: ProjectMembersPageProps) {
  const [members, setMembers] = useState<ProjectMemberSummary[]>([]);
  const [requests, setRequests] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isLeader = project.my_membership.project_role === "LEADER";

  async function loadData() {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const [membersRes, requestsRes] = await Promise.all([
        fetchProjectMembers(project.id),
        isLeader ? fetchProjectJoinRequests(project.id) : Promise.resolve({ items: [] }),
      ]);
      setMembers(membersRes.items);
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
    if (!confirm(`정말로 이 요청을 ${status === "APPROVED" ? "승인" : "거절"}하시겠습니까?`)) {
      return;
    }
    try {
      await reviewProjectJoinRequest(project.id, requestId, { request_status: status });
      await loadData();
    } catch (e: any) {
      alert(e.message || "요청을 처리하는데 실패했습니다.");
    }
  }

  if (isLoading) {
    return <section className="surface-panel"><p>로딩 중...</p></section>;
  }

  return (
    <section className="surface-panel" style={{ padding: "2rem" }}>
      <h1>팀원 페이지</h1>
      
      {errorMessage && <div className="error-message" style={{ color: "red", marginBottom: "1rem" }}>{errorMessage}</div>}

      <div style={{ marginBottom: "2rem" }}>
        <h2>현재 팀원 ({members.length}명)</h2>
        <ul style={{ listStyle: "none", padding: 0 }}>
          {members.map(m => (
            <li key={m.project_member_id} style={{ padding: "0.5rem", borderBottom: "1px solid var(--color-gray-200)" }}>
              <strong>{m.name}</strong> ({m.email}) - {m.position_label} [{m.project_role}]
            </li>
          ))}
        </ul>
      </div>

      {isLeader && (
        <div>
          <h2>참여 요청 ({requests.length}건)</h2>
          {requests.length === 0 ? (
            <p style={{ color: "var(--color-gray-500)" }}>대기 중인 참여 요청이 없습니다.</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0 }}>
              {requests.map(r => (
                <li key={r.id} style={{ padding: "1rem", border: "1px solid var(--color-gray-200)", marginBottom: "1rem", borderRadius: "8px" }}>
                  <div style={{ marginBottom: "0.5rem" }}>
                    <strong>{r.requester_name}</strong> ({r.requester_email})님이 참여를 요청했습니다.
                  </div>
                  {r.request_message && (
                    <div style={{ marginBottom: "0.5rem", color: "var(--color-gray-600)" }}>
                      메시지: {r.request_message}
                    </div>
                  )}
                  {r.requested_position_label && (
                    <div style={{ marginBottom: "1rem", color: "var(--color-gray-600)" }}>
                      희망 직책/역할: {r.requested_position_label}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button 
                      onClick={() => handleReview(r.id, "APPROVED")}
                      style={{ padding: "0.5rem 1rem", backgroundColor: "blue", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
                    >
                      승인
                    </button>
                    <button 
                      onClick={() => handleReview(r.id, "REJECTED")}
                      style={{ padding: "0.5rem 1rem", backgroundColor: "red", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
                    >
                      거절
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
