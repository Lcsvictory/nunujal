import "./LandingPage.css";

type LandingPageProps = {
  onMoveToLogin: () => void;
};

export function LandingPage({ onMoveToLogin }: LandingPageProps) {
  return (
    <div className="landing-layout">
      {/* Navbar */}
      <nav className="landing-nav">
        <div className="landing-nav-logo">
          <span className="hero-badge">NunuJal</span>
        </div>
        <button type="button" className="button button-ghost" onClick={onMoveToLogin}>
          로그인
        </button>
      </nav>

      <main className="landing-main">
        {/* Hero Section */}
        <section className="landing-hero">
          <div className="landing-hero-content">
            <span className="landing-hero-badge">Welcome to Workspace</span>
            <h1 className="landing-hero-title">
              성공적인 팀 프로젝트를 위한<br />
              <span className="highlight-text">스마트한 협업 도구</span>
            </h1>
            <p className="landing-hero-subtitle">
              일정 관리부터 할일 분배, 그리고 팀원들의 기여도까지.<br />
              NunuJal 워크스페이스에서 간편하게 시작하세요.
            </p>
            <div className="landing-hero-actions">
              <button type="button" className="button button-primary button-large" onClick={onMoveToLogin}>
                무료로 시작하기
              </button>
            </div>
          </div>
          
          <div className="landing-hero-visual">
            <div className="visual-mockup surface-panel">
              <div className="mockup-header">
                <div className="mockup-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
              <div className="mockup-body">
                 <div className="mockup-sidebar"></div>
                 <div className="mockup-content">
                    <div className="mockup-card"></div>
                    <div className="mockup-card"></div>
                    <div className="mockup-card highlight"></div>
                 </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="landing-features">
          <h2 className="section-title">팀의 생산성을 높이는 핵심 기능</h2>
          <div className="features-grid">
            <div className="feature-card surface-panel">
              <div className="feature-icon">📊</div>
              <h3>간트차트 기반 일정 관리</h3>
              <p>시작일과 종료일, 선후행 태스크를 직관적으로 파악하고 효율적인 타임라인을 구성해보세요.</p>
            </div>
            
            <div className="feature-card surface-panel">
              <div className="feature-icon">📋</div>
              <h3>칸반 보드 할일 관리</h3>
              <p>진행 예정, 진행 중, 완료 등 태스크 상태를 드래그 앤 드롭으로 간편하게 조작할 수 있습니다.</p>
            </div>

            <div className="feature-card surface-panel">
              <div className="feature-icon">👥</div>
              <h3>팀원 기여도 및 권한 관리</h3>
              <p>초대 코드를 통한 참여, 역할 부여, 그리고 각각의 프로젝트별 성과와 활동을 한눈에 파악하세요.</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <p>© 2026 NunuJal Capstone Project. All rights reserved.</p>
      </footer>
    </div>
  );
}
