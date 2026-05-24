import { useEffect, useState } from "react";
import { ErrorPage } from "./features/auth/ErrorPage";
import { LandingPage } from "./features/auth/LandingPage";
import { LoginPage } from "./features/auth/LoginPage";
import { MyPage } from "./features/auth/MyPage";
import { ChatWidget } from "./features/chat/ChatWidget";
import { ProjectOverviewPage } from "./features/projects/ProjectOverviewPage";
import { ProjectsPage } from "./features/projects/ProjectsPage";
import { isKnownPath, navigate, parseLocation } from "./lib/router";

function withChatWidget(content: JSX.Element) {
  return (
    <>
      {content}
      <ChatWidget />
    </>
  );
}

export default function App() {
  const [{ screen, params, projectId }, setRoute] = useState(() =>
    parseLocation(window.location),
  );

  useEffect(() => {
    if (!isKnownPath(window.location.pathname)) {
      window.history.replaceState({}, "", "/");
    }

    const handleRouteChange = () => setRoute(parseLocation(window.location));

    window.addEventListener("popstate", handleRouteChange);
    return () => window.removeEventListener("popstate", handleRouteChange);
  }, []);

  if (screen === "login") {
    return <LoginPage params={params} />;
  }

  if (screen === "error") {
    return <ErrorPage params={params} />;
  }

  if (screen === "projects") {
    return withChatWidget(
      <ProjectsPage
        onMoveToLogin={() => navigate("/login")}
        onOpenProject={(nextProjectId) => navigate(`/projects/${nextProjectId}`)}
      />,
    );
  }

  if (screen === "my-page") {
    return withChatWidget(
      <MyPage
        onMoveBack={() => navigate("/projects")}
        onMoveToLogin={() => navigate("/login")}
      />,
    );
  }

  if (screen === "project-overview") {
    return withChatWidget(
      <ProjectOverviewPage
        projectId={projectId}
        onMoveToProjects={() => navigate("/projects")}
      />,
    );
  }

  return <LandingPage onMoveToLogin={() => navigate("/login")} />;
}
