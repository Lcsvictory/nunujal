import { useEffect, useMemo, useState } from "react";

type AppScreen = "landing" | "login" | "project-select";
type AuthStatus = "idle" | "success" | "error";

type AuthUser = {
  id: number;
  email: string;
  name: string;
  provider: string;
  profile_image_url?: string | null;
  status: string;
};

const backendBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8028";

function parseLocation(location: Location): { screen: AppScreen; params: URLSearchParams } {
  let normalizedPath: "/" | "/login" | "/projects/select" = "/";

  if (location.pathname === "/login") {
    normalizedPath = "/login";
  } else if (location.pathname === "/projects/select") {
    normalizedPath = "/projects/select";
  }

  const screenMap: Record<typeof normalizedPath, AppScreen> = {
    "/": "landing",
    "/login": "login",
    "/projects/select": "project-select",
  };

  return {
    screen: screenMap[normalizedPath],
    params: new URLSearchParams(location.search),
  };
}

function navigate(path: "/" | "/login" | "/projects/select") {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function getGoogleLoginUrl(): string {
  return `${backendBaseUrl}/api/auth/google/login`;
}

function LandingPage({ onMoveToLogin }: { onMoveToLogin: () => void }) {
  return (
    <div className="auth-shell">
      <main className="auth-stage">
        <section className="auth-brand-block">
          <div className="auth-logo">N</div>
          <h1>NuNuJal</h1>
          <p>함께 만드는 팀 프로젝트 워크스페이스</p>
        </section>

        <section className="landing-card">
          <span className="landing-badge">Google 로그인 전용</span>
          <h2>단순한 로그인 흐름부터 시작합니다</h2>
          <p>
            현재 연습 범위는 Google 로그인, 인증된 사용자 확인, 그리고 프로젝트 진입 화면 구성에
            집중되어 있습니다.
          </p>

          <button type="button" className="primary-cta" onClick={onMoveToLogin}>
            로그인 화면으로 이동
          </button>
        </section>

        <footer className="auth-footer">© 2026 NuNuJal. All rights reserved.</footer>
      </main>
    </div>
  );
}

function LoginPage({ params }: { params: URLSearchParams }) {
  const authStatus = (params.get("auth") as AuthStatus | null) ?? "idle";
  const errorMessage = params.get("message");

  const statusMessage = useMemo(() => {
    if (authStatus === "success") {
      return "로그인이 완료되었습니다. 프로젝트 선택 화면으로 이동합니다.";
    }

    if (authStatus === "error") {
      return errorMessage ?? "Google 로그인에 실패했습니다. OAuth 설정과 콜백 URL을 확인하세요.";
    }

    return "Google 계정으로 로그인하세요.";
  }, [authStatus, errorMessage]);

  return (
    <div className="auth-shell">
      <main className="auth-stage">
        <section className="auth-brand-block">
          <div className="auth-logo">N</div>
          <h1>NuNuJal</h1>
          <p>함께 만드는 팀 프로젝트 워크스페이스</p>
        </section>

        <section className="login-card-v2">
          <header className="login-card-header">
            <h2>로그인</h2>
            <p>{statusMessage}</p>
          </header>

          <a className="social-button social-button-google" href={getGoogleLoginUrl()}>
            <svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" className="google-icon">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"></path>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"></path>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"></path>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path>
              <path fill="none" d="M0 0h48v48H0z"></path>
            </svg>
            <span className="google-button-text">
              <strong>Google</strong> 계정으로 로그인
            </span>
          </a>

          <div className="legal-copy">
            계속 진행하면 OAuth 로그인 연습 흐름의 첫 단계에 동의한 것으로 간주합니다.
          </div>
        </section>

        <footer className="auth-footer">© 2026 NuNuJal. All rights reserved.</footer>
      </main>
    </div>
  );
}

function ProjectSelectionPage({ onMoveToLogin }: { onMoveToLogin: () => void }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadCurrentUser() {
      try {
        const response = await fetch(`${backendBaseUrl}/api/auth/me`, {
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error("현재 사용자 정보를 불러오지 못했습니다.");
        }

        const data = (await response.json()) as { authenticated: boolean; user: AuthUser | null };
        if (!isMounted) {
          return;
        }

        if (!data.authenticated || !data.user) {
          setUser(null);
          setErrorMessage("인증된 세션이 없습니다. 다시 로그인하세요.");
          return;
        }

        setUser(data.user);
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message = error instanceof Error ? error.message : "현재 사용자 정보를 불러오지 못했습니다.";
        setUser(null);
        setErrorMessage(message);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadCurrentUser();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="project-shell">
      <main className="project-stage">
        <section className="project-hero">
          <div className="project-hero-copy">
            <span className="project-kicker">프로젝트 선택</span>
            <h1>다음으로 진입할 프로젝트를 선택하세요</h1>
            <p>
              이 화면은 로그인 이후 처음 도착하는 페이지입니다. 다음 단계에서 실제 프로젝트 목록 API를
              연결하면 됩니다.
            </p>
          </div>

          <aside className="profile-card">
            <div className="profile-avatar">
              {user?.profile_image_url ? (
                <img src={user.profile_image_url} alt={user.name} />
              ) : (
                <span>{user?.name?.slice(0, 1).toUpperCase() ?? "N"}</span>
              )}
            </div>
            <div className="profile-meta">
              <strong>{user?.name ?? "로그인되지 않은 사용자"}</strong>
              <span>{user?.email ?? "로그인이 필요합니다"}</span>
              <span>{user ? `${user.provider} · ${user.status}` : "세션 정보를 확인할 수 없습니다"}</span>
            </div>
          </aside>
        </section>

        <section className="project-panel">
          <header className="project-panel-header">
            <div>
              <h2>프로젝트 목록</h2>
              <p>REST 프로젝트 목록 API를 연결하기 전까지는 임시 카드만 표시합니다.</p>
            </div>
          </header>

          {isLoading ? <div className="project-empty-state">인증된 사용자 정보를 불러오는 중입니다...</div> : null}

          {!isLoading && errorMessage ? (
            <div className="project-empty-state">
              <p>{errorMessage}</p>
              <button type="button" className="secondary-cta" onClick={onMoveToLogin}>
                로그인 화면으로 돌아가기
              </button>
            </div>
          ) : null}

          {!isLoading && !errorMessage ? (
            <div className="project-grid">
              <article className="project-card">
                <span className="project-card-tag">연습 흐름</span>
                <h3>프로젝트 목록 API</h3>
                <p>`GET /api/projects`를 연결해서 이 임시 카드를 실제 데이터로 교체합니다.</p>
                <button type="button" className="project-card-button" disabled>
                  API 준비 중
                </button>
              </article>

              <article className="project-card">
                <span className="project-card-tag">다음 단계</span>
                <h3>프로젝트 생성</h3>
                <p>선택 화면이 안정되면 REST 엔드포인트와 생성 폼을 추가하면 됩니다.</p>
                <button type="button" className="project-card-button" disabled>
                  폼 준비 중
                </button>
              </article>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const [{ screen, params }, setRoute] = useState(() => parseLocation(window.location));

  useEffect(() => {
    const validPaths = ["/", "/login", "/projects/select"];
    if (!validPaths.includes(window.location.pathname)) {
      window.history.replaceState({}, "", "/");
    }

    const handleRouteChange = () => setRoute(parseLocation(window.location));

    window.addEventListener("popstate", handleRouteChange);
    return () => window.removeEventListener("popstate", handleRouteChange);
  }, []);

  const moveToLogin = () => {
    navigate("/login");
  };

  if (screen === "login") {
    return <LoginPage params={params} />;
  }

  if (screen === "project-select") {
    return <ProjectSelectionPage onMoveToLogin={moveToLogin} />;
  }

  return <LandingPage onMoveToLogin={moveToLogin} />;
}
