import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1b1f23",
        teal: { DEFAULT: "#0f5e63", dark: "#0a4448", light: "#e6f1f1" },
        sale: "#c8102e",
        sand: "#f6f3ee",
      },
      fontFamily: { sans: ["var(--font-sans)", "system-ui", "sans-serif"], display: ["var(--font-display)", "Georgia", "serif"] },
    },
  },
  plugins: [],
} satisfies Config;
