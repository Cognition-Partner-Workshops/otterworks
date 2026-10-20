
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

const clientApp = path.resolve(__dirname, "../../../../frontend/client-app");

// The screens only ever talk to /api/claims-screens; CLAIMS_API picks which claims_api.py (golden or camel) answers
// and CLAIMS_API_TOKEN is the bearer token the proxy sends (a reader token gets claimant PII masked).
export default defineConfig({
  plugins: [react()],
  publicDir: path.join(clientApp, "public"),
  resolve: { alias: { "@client-app": path.join(clientApp, "src") } },
  server: {
    port: Number(process.env.PORT ?? 5180),
    strictPort: true,
    fs: { allow: [__dirname, clientApp] },
    proxy: {
      "/api/claims-screens": {
        target: process.env.CLAIMS_API ?? "http://127.0.0.1:8095",
        headers: process.env.CLAIMS_API_TOKEN ? { Authorization: `Bearer ${process.env.CLAIMS_API_TOKEN}` } : {},
      },
    },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"] },
});
