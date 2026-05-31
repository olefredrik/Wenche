import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// I dev proxer vi /api til den hostede FastAPI-backenden, slik at nettleseren
// ser alt som samme origin (ingen CORS, cookies virker rett fram).
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
