import type { IncomingMessage, ServerResponse } from "node:http";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

function redirectEnvRequests(): Plugin {
  const redirect = (req: IncomingMessage, res: ServerResponse) => {
    const pathname = new URL(req.url ?? "/", "http://localhost").pathname;

    if (!/^\/\.env(?:[.\w-]*)?$/.test(pathname)) {
      return false;
    }

    res.statusCode = 302;
    res.setHeader("Location", "/");
    res.end();
    return true;
  };

  return {
    name: "redirect-env-requests",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (redirect(req, res)) {
          return;
        }

        next();
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        if (redirect(req, res)) {
          return;
        }

        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), redirectEnvRequests()],
  server: {
    host: '0.0.0.0',
    port: 5073,
    allowedHosts: ['nunujal.o-r.kr'],
    hmr: {
      clientPort: 443,
      host: 'nunujal.o-r.kr'
    }
  },
});
