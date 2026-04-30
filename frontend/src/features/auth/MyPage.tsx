import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ApiError } from "../../lib/api";
import { updateProjectMember } from "../projects/api";
import type { ProjectMembership } from "../projects/types";
import { fetchCurrentUser } from "./api";
import type { AuthUser } from "./types";

type MyPageProps = {
  embedded?: boolean;
  initialUser?: AuthUser | null;
  projectId?: number;
  membership?: ProjectMembership | null;
  onUserUpdated?: (user: AuthUser) => void;
  onMembershipUpdated?: (membership: ProjectMembership) => void;
  onMoveBack?: () => void;
  onMoveToLogin?: () => void;
};

type ProfileFormState = {
  role: string;
};

function buildInitials(name: string | undefined): string {
  return name?.trim().slice(0, 1).toUpperCase() || "N";
}

function toFormState(user: AuthUser | null): ProfileFormState {
  return {
    role: "",
  };
}

export function MyPage({
  embedded = false,
  initialUser = null,
  projectId,
  membership = null,
  onUserUpdated,
  onMembershipUpdated,
  onMoveBack,
  onMoveToLogin,
}: MyPageProps) {
  const [user, setUser] = useState<AuthUser | null>(initialUser);
  const [formState, setFormState] = useState<ProfileFormState>(() => ({ role: membership?.position_label ?? "" }));
  const [isLoading, setIsLoading] = useState(!initialUser);
  const [isSaving, setIsSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!initialUser) {
      return;
    }

    setUser(initialUser);
  }, [initialUser]);

  useEffect(() => {
    setFormState({ role: membership?.position_label ?? "" });
  }, [membership]);

  useEffect(() => {
    let isDisposed = false;

    async function loadUser() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const response = await fetchCurrentUser();
        if (isDisposed) {
          return;
        }
        if (!response.authenticated || !response.user) {
          setUser(null);
          setErrorMessage("로그인이 필요합니다.");
          return;
        }
        setUser(response.user);
      } catch (error) {
        if (!isDisposed) {
          setErrorMessage(error instanceof ApiError ? error.message : "내 정보를 불러오지 못했습니다.");
        }
      } finally {
        if (!isDisposed) {
          setIsLoading(false);
        }
      }
    }

    void loadUser();
    return () => {
      isDisposed = true;
    };
  }, []);

  const hasChanges = useMemo(() => {
    if (!user) {
      return false;
    }

    return formState.role.trim() !== (membership?.position_label ?? "");
  }, [formState.role, membership, user]);

  const handleCancel = () => {
    setFormState({ role: membership?.position_label ?? "" });
    setIsEditing(false);
    setErrorMessage(null);
    setNotice(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) {
      return;
    }

    if (!projectId || !membership) {
      setErrorMessage("프로젝트 안에서만 역할을 수정할 수 있습니다.");
      return;
    }

    const role = formState.role.trim();
    if (!role) {
      setErrorMessage("역할은 비워둘 수 없습니다.");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    setNotice(null);
    try {
      const response = await updateProjectMember(projectId, membership.project_member_id, {
        position_label: role,
      });
      setFormState({ role: response.member.position_label });
      onMembershipUpdated?.(response.member);
      setIsEditing(false);
      setNotice("역할이 저장되었습니다.");
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "역할을 저장하지 못했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  const content = (
    <div className="mypage-layout">
      <section className="surface-panel mypage-profile-card">
        <div className="mypage-avatar">
          {user?.profile_image_url ? (
            <img src={user.profile_image_url} alt={`${user.name} 프로필`} />
          ) : (
            <span>{buildInitials(user?.name)}</span>
          )}
        </div>
        <div className="mypage-profile-copy">
          <p className="section-label">my page</p>
          <h1>{user?.name ?? "내 정보"}</h1>
          <p>{user?.email ?? "로그인 정보를 확인하는 중입니다."}</p>
        </div>
      </section>

      <section className="surface-panel mypage-detail-card">
        <div className="section-heading">
          <div>
            <p className="section-label">profile</p>
            <h2>내 정보</h2>
          </div>
          {!isEditing && user && projectId && membership ? (
            <button type="button" className="button button-secondary" onClick={() => setIsEditing(true)}>
              역할 수정
            </button>
          ) : null}
        </div>

        {isLoading ? (
          <div className="mypage-skeleton">
            <div className="skeleton-line skeleton-line-short" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}

        {!isLoading && !user ? (
          <div className="empty-panel">
            <h2>로그인이 필요합니다</h2>
            <p>{errorMessage ?? "내 정보를 보려면 먼저 로그인해 주세요."}</p>
            {onMoveToLogin ? (
              <button type="button" className="button button-primary" onClick={onMoveToLogin}>
                로그인 화면으로 이동
              </button>
            ) : null}
          </div>
        ) : null}

        {!isLoading && user ? (
          <form className="overlay-form mypage-form" onSubmit={handleSubmit}>
            <dl className="mypage-readonly-grid">
              <div>
                <dt>이름</dt>
                <dd>{user.name}</dd>
              </div>
              <div>
                <dt>이메일</dt>
                <dd>{user.email}</dd>
              </div>
              <div>
                <dt>역할</dt>
                <dd>{membership?.position_label ?? "프로젝트에서 확인 가능"}</dd>
              </div>
            </dl>

            {isEditing ? (
              <label className="field">
                <span>역할</span>
                <input
                  value={formState.role}
                  onChange={(event) => setFormState({ role: event.target.value })}
                  disabled={isSaving}
                  maxLength={100}
                  placeholder="예: 프론트엔드, 자료 조사, 팀장"
                />
              </label>
            ) : null}

            {notice ? <p className="form-feedback">{notice}</p> : null}
            {errorMessage ? <p className="form-feedback form-feedback-error">{errorMessage}</p> : null}

            {isEditing ? (
              <div className="overlay-actions">
                <button type="button" className="button button-ghost" onClick={handleCancel} disabled={isSaving}>
                  취소
                </button>
                <button type="submit" className="button button-primary" disabled={isSaving || !hasChanges}>
                  {isSaving ? "저장 중..." : "저장"}
                </button>
              </div>
            ) : null}
          </form>
        ) : null}
      </section>
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <div className="mypage-shell">
      <header className="workspace-topbar">
        <div className="workspace-brand">
          <div className="workspace-brand-mark">N</div>
          <div className="workspace-brand-copy">
            <strong>누누잘</strong>
            <span>내 정보 관리</span>
          </div>
        </div>
        <div className="workspace-topbar-actions">
          {onMoveBack ? (
            <button type="button" className="button button-secondary" onClick={onMoveBack}>
              돌아가기
            </button>
          ) : null}
        </div>
      </header>
      <main className="mypage-content">{content}</main>
    </div>
  );
}
