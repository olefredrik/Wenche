// Vitest for hele frontend-workspacet: rene funksjoner og komponenter i packages/ui, pluss
// røyktester av appene. Kjøres med `npm test` (og i CI). jsdom gir DOM-et komponentene trenger.
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@wenche/ui": fileURLToPath(new URL("./packages/ui/src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: [
      "packages/ui/src/**/*.test.{ts,tsx}",
      "hosted/web/src/**/*.test.{ts,tsx}",
      "wenche/web/frontend/src/**/*.test.{ts,tsx}",
    ],
  },
});
