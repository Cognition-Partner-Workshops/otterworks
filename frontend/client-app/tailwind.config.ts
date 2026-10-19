import type { Config } from "tailwindcss";

// Halvergate Bank theme.
const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    borderRadius: {
      none: "0",
      sm: "1px",
      DEFAULT: "2px",
      md: "2px",
      lg: "2px",
      xl: "2px",
      "2xl": "2px",
      "3xl": "2px",
      full: "9999px",
    },
    extend: {
      colors: {
        otter: {
          50: "#f3f6f4",
          100: "#e3ebe6",
          200: "#c3d5ca",
          300: "#98b8a5",
          400: "#5f8f74",
          500: "#2f6b4f",
          600: "#1d5340",
          700: "#174433",
          800: "#123628",
          900: "#0d281e",
        },
        accent: {
          400: "#c9a24a",
          500: "#b38a2e",
          600: "#946f1f",
        },
      },
      fontFamily: {
        sans: ['"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
        serif: ["Georgia", "Cambria", '"Times New Roman"', "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
