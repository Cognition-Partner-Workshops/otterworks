// Dev-server proxy mirroring nginx.conf.template: forwards /api/* to the API gateway so
// `ng serve` stays same-origin (no CORS), exactly like the production nginx image.
// Override the gateway with API_GATEWAY_URL (same knob as the client-app dev server).
export default {
  // Mirrors nginx: the chaos endpoint needs X-Chaos-Secret, added server-side.
  "/api/v1/admin/chaos": {
    target: process.env.API_GATEWAY_URL || "http://localhost:8080",
    changeOrigin: true,
    headers: { "X-Chaos-Secret": process.env.CHAOS_SECRET || "" },
  },
  "/api": {
    target: process.env.API_GATEWAY_URL || "http://localhost:8080",
    changeOrigin: true,
  },
};
