import { navigate } from "../../lib/router";

type ErrorPageProps = {
  params: URLSearchParams;
};

function getDefaultMessage(code: string | null): string {
  if (code === "401") {
    return "세션이 만료되었거나 다른 기기에서 로그인되어 로그아웃되었습니다.";
  }

  if (code === "network") {
    return "서버에 연결하지 못했습니다. 네트워크 또는 서버 상태를 확인해 주세요.";
  }

  return "서버에서 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function ErrorPage({ params }: ErrorPageProps) {
  const code = params.get("code");
  const message = params.get("message") ?? getDefaultMessage(code);

  return (
    <div className="auth-shell">
      <main className="auth-stage">
        <section className="error-card surface-panel">
          <span className="hero-badge">Error</span>
          <h1>문제가 발생했습니다</h1>
          <p>{message}</p>
          {code ? <span className="error-code">오류 코드 {code}</span> : null}
          <div className="auth-actions">
            <button type="button" className="button button-primary" onClick={() => navigate("/")}>
              홈 화면으로 이동
            </button>
            <button type="button" className="button button-secondary" onClick={() => navigate("/login")}>
              로그인 화면으로 이동
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
