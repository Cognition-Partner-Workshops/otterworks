import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextVitals,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
  {
    rules: {
      // The fetch-on-mount loaders predate this React 19.2 compiler rule;
      // surfaced as warnings until the components move to a data library.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);
