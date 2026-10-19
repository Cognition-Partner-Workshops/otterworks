import type { Config } from "tailwindcss";

// Halvenmoor Health theme: teal primary, coral accent, softened corners, system sans stack.
const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    borderRadius: {
      none: "0",
      sm: "2px",
      DEFAULT: "4px",
      md: "4px",
      lg: "6px",
      xl: "8px",
      "2xl": "10px",
      "3xl": "12px",
      full: "9999px",
    },
    extend: {
      colors: {
        otter: {
          50: "#f1f8f8",
          100: "#dcefef",
          200: "#b5dcdc",
          300: "#84c2c3",
          400: "#4c9fa1",
          500: "#2a8083",
          600: "#13686c",
          700: "#0f5559",
          800: "#0d4548",
          900: "#0a3537",
        },
        accent: {
          400: "#ec8a6c",
          500: "#e0714f",
          600: "#c25a3a",
        },
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
