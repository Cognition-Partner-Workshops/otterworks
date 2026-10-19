import type { Config } from "tailwindcss";

// Quillstead Capital theme: deep green primary, brass accent, and serif headings.
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
          50: "#f2f6f4",
          100: "#e1ebe6",
          200: "#c2d6cc",
          300: "#96b8a8",
          400: "#5f8f7a",
          500: "#2f6b55",
          600: "#1d4a3f",
          700: "#173d34",
          800: "#12312a",
          900: "#0c231e",
        },
        accent: {
          400: "#c9a25a",
          500: "#b8893a",
          600: "#96702e",
        },
      },
      fontFamily: {
        sans: ['"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
        serif: ['Georgia', '"Times New Roman"', "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
