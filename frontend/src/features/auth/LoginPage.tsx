import { useMemo } from "react";
import { getGoogleLoginUrl } from "../../lib/api";

type AuthStatus = "idle" | "success" | "error";

type LoginPageProps = {
  params: URLSearchParams;
};

export function LoginPage({ params }: LoginPageProps) {
  const authStatus = (params.get("auth") as AuthStatus | null) ?? "idle";
  const errorMessage = params.get("message");

  const statusMessage = useMemo(() => {
    if (authStatus === "success") {
      return "로그인이 완료되었습니다. 프로젝트 화면으로 이동합니다.";
    }

    if (authStatus === "error") {
      return errorMessage ?? "Google 로그인에 실패했습니다. OAuth 설정과 콜백 URL을 확인하세요.";
    }

    return "Google 계정으로 로그인해 프로젝트 화면에 진입하세요.";
  }, [authStatus, errorMessage]);

  return (
    <div className="auth-shell">
      <main className="auth-stage">
        <section className="auth-hero auth-hero-compact">
          <span className="hero-badge">Google OAuth</span>
          <h1>로그인</h1>
          <p>{statusMessage}</p>
        </section>

        <section className="login-card">
          <a className="button button-surface button-google" href={getGoogleLoginUrl()}>
            <span className="google-mark" aria-hidden="true">
              G
            </span>
            Google 계정으로 로그인
          </a>

          <div className="login-divider" aria-hidden="true" />

          <p className="login-copy">
            실습 환경에서는 테스트 더미 계정 로그인도 사용할 수 있지만, 기본 흐름은
            Google OAuth를 기준으로 유지합니다.
          </p>
        </section>
      </main>
    </div>
  );
}
