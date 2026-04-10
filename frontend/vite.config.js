import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
function redirectEnvRequests() {
    var redirect = function (req, res) {
        var _a;
        var pathname = new URL((_a = req.url) !== null && _a !== void 0 ? _a : "/", "http://localhost").pathname;
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
        configureServer: function (server) {
            server.middlewares.use(function (req, res, next) {
                if (redirect(req, res)) {
                    return;
                }
                next();
            });
        },
        configurePreviewServer: function (server) {
            server.middlewares.use(function (req, res, next) {
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
