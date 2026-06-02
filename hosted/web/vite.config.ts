import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Delt designsystem konsumeres som kildekode via alias (ingen separat byggesteg),
// så Vite + Tailwind kompilerer det som del av app-grafen.
const wencheUi = fileURLToPath(new URL("../../packages/ui/src", import.meta.url));

// I dev proxer vi /api til den hostede FastAPI-backenden, slik at nettleseren
// ser alt som samme origin (ingen CORS, cookies virker rett fram).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@wenche/ui": wencheUi } },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8077",
        changeOrigin: true,
      },
    },
  },
});
