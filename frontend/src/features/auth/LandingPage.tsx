type LandingPageProps = {
  onMoveToLogin: () => void;
};

export function LandingPage({ onMoveToLogin }: LandingPageProps) {
  return (
    <div className="auth-shell">
      <main className="auth-stage">
        <section className="auth-hero">
          <span className="hero-badge">NunuJal</span>
          <h1>프로젝트 기여 관리 연습용 워크스페이스</h1>
          <p>
            지금 단계에서는 완성형 서비스보다 화면 구조와 API 흐름을 차근차근
            만드는 데 집중합니다. 로그인 이후 프로젝트 선택, 생성, 참여, 개요
            화면을 한 흐름으로 이어갑니다.
          </p>
          <div className="auth-actions">
            <button type="button" className="button button-primary" onClick={onMoveToLogin}>
              로그인 화면으로 이동
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
