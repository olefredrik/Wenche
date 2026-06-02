import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Den bygde SPA-en serveres av FastAPI fra wenche/web/static i prod. I dev proxer vi /api
// til den lokale backenden (kjør den med `python -m wenche.web.dev`), så alt er same-origin.
const wencheUi = fileURLToPath(new URL("../../../packages/ui/src", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@wenche/ui": wencheUi } },
  // Bygg til wenche/web/static så FastAPI (og wheelen) finner den ferdige SPA-en.
  build: { outDir: fileURLToPath(new URL("../static", import.meta.url)), emptyOutDir: true },
  server: {
    port: 5174,
    proxy: {
      "/api": { target: "http://127.0.0.1:8080", changeOrigin: true },
    },
  },
});
