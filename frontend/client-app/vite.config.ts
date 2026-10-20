/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import pkg from "./package.json" with { type: "json" };

// Insurance-only mobile claims screen, kept outside the shell's src tree.
const mobileClaims = path.resolve(__dirname, "../../industries/insurance/mobile-claims");

// Dev/preview proxy forwards /api/v1/* to the API gateway (same-origin, no CORS),
// mirroring the old Next.js middleware rewrite. Production uses nginx for the same job.
const apiProxy = {
  "/api/v1": {
    target: process.env.API_GATEWAY_URL || "http://localhost:8080",
    changeOrigin: true,
  },
};
const billingProxy = {
  "/billing-api": {
    target: process.env.BILLING_SERVICE_URL || "http://localhost:12109",
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/billing-api/, ""),
  },
};

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@claims": path.join(mobileClaims, "src"),
    },
    // Resolve the claims module's bare imports from this app's node_modules.
    dedupe: [
      "react",
      "react-dom",
      "react-hook-form",
      "@hookform/resolvers",
      "zod",
      "lucide-react",
      "axios",
      "@capacitor/core",
      "@testing-library/react",
      "@testing-library/jest-dom",
    ],
  },
  server: {
    port: 3000,
    proxy: { ...apiProxy, ...billingProxy },
    fs: { allow: [".", mobileClaims] },
  },
  preview: {
    port: 3000,
    proxy: { ...apiProxy, ...billingProxy },
  },
  test: {
    include: ["src/**/*.{test,spec}.{ts,tsx}", `${mobileClaims}/src/**/*.{test,spec}.{ts,tsx}`],
    setupFiles: ["src/test-setup.ts"],
    globals: true,
    environment: "jsdom",
  },
});
