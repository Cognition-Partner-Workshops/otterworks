// `ng serve` forwards /bff/* to a locally running BFF so the portal stays same-origin,
// exactly like the BFF-served production build. Override with BFF_URL.
export default {
  "/bff": {
    target: process.env.BFF_URL || "http://localhost:5080",
    changeOrigin: true,
  },
};
