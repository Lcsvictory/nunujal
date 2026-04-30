import { useEffect, useState } from "react";
import { LandingPage } from "./features/auth/LandingPage";
import { LoginPage } from "./features/auth/LoginPage";
import { MyPage } from "./features/auth/MyPage";
import { ProjectOverviewPage } from "./features/projects/ProjectOverviewPage";
import { ProjectsPage } from "./features/projects/ProjectsPage";
import { isKnownPath, navigate, parseLocation } from "./lib/router";

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

  if (screen === "projects") {
    return (
      <ProjectsPage
        onMoveToLogin={() => navigate("/login")}
        onOpenProject={(nextProjectId) => navigate(`/projects/${nextProjectId}`)}
      />
    );
  }

  if (screen === "my-page") {
    return (
      <MyPage
        onMoveBack={() => navigate("/projects")}
        onMoveToLogin={() => navigate("/login")}
      />
    );
  }

  if (screen === "project-overview") {
    return (
      <ProjectOverviewPage
        projectId={projectId}
        onMoveToProjects={() => navigate("/projects")}
      />
    );
  }

  return <LandingPage onMoveToLogin={() => navigate("/login")} />;
}
