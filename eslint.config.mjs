// ESLint for hele frontend-workspacet: packages/ui, hosted/web og wenche/web/frontend.
// Kjøres med `npm run lint` (og i CI). Typesjekk er en egen kommando (`npm run typecheck`).
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default defineConfig(
  {
    // Bare vår egen TS/TSX: bygde filer, avhengigheter og Python-venvet (mkdocs-material
    // leverer JS-filer der) skal ikke lintes.
    ignores: [
      "**/dist/**",
      "**/node_modules/**",
      "**/.venv/**",
      ".nicegui/**",
      "wenche/web/static/**",
      "site/**",
      "**/.vite/**",
    ],
  },
  ...tseslint.configs.recommended,
  reactHooks.configs.flat.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser } },
    rules: {
      // `any` finnes fortsatt mange steder (config-objektet, API-svar). Typing av API-laget er
      // leveranse 6 i kodegjennomgangen; til da er det en advarsel, ikke en feil.
      "@typescript-eslint/no-explicit-any": "warn",
      // Regelen flagger også en async laster som setter state først etter await (Oppsett.tsx),
      // som er greit. Advarsel til mønsteret er lagt om, så den ikke blokkerer.
      "react-hooks/set-state-in-effect": "warn",
      // Et navn med `_` foran er bevisst ubrukt (f.eks. en nøkkel som plukkes bort fra et objekt).
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", ignoreRestSiblings: true },
      ],
    },
  },
  {
    files: ["**/vite.config.ts", "vitest.config.ts", "eslint.config.mjs"],
    languageOptions: { globals: { ...globals.node } },
  },
);
