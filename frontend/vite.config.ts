import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
