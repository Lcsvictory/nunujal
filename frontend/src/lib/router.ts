export type AppScreen = "landing" | "login" | "projects" | "project-overview" | "my-page";

export type ParsedRoute = {
  screen: AppScreen;
  params: URLSearchParams;
  projectId: number | null;
};

export function parseLocation(location: Location): ParsedRoute {
  const projectDetailMatch = location.pathname.match(/^\/projects\/(\d+)$/);

  if (location.pathname === "/login") {
    return {
      screen: "login",
      params: new URLSearchParams(location.search),
      projectId: null,
    };
  }

  if (location.pathname === "/projects") {
    return {
      screen: "projects",
      params: new URLSearchParams(location.search),
      projectId: null,
    };
  }

  if (location.pathname === "/my-page") {
    return {
      screen: "my-page",
      params: new URLSearchParams(location.search),
      projectId: null,
    };
  }

  if (projectDetailMatch) {
    return {
      screen: "project-overview",
      params: new URLSearchParams(location.search),
      projectId: Number(projectDetailMatch[1]),
    };
  }

  return {
    screen: "landing",
    params: new URLSearchParams(location.search),
    projectId: null,
  };
}

export function isKnownPath(pathname: string): boolean {
  return pathname === "/" || pathname === "/login" || pathname === "/projects" || pathname === "/my-page" || /^\/projects\/\d+$/.test(pathname);
}

export function navigate(path: string): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
