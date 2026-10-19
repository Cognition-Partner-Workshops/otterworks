import type { Config } from "tailwindcss";

// Tamberlyn Pictures theme: deep plum primary, flat square corners, coral
// accent, humanist sans stack. The `otter` key is kept so class names don't churn.
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
          50: "#f6f3f8",
          100: "#ebe4f0",
          200: "#d4c5de",
          300: "#b29cc3",
          400: "#8a6ea3",
          500: "#654a80",
          600: "#45305e",
          700: "#36244b",
          800: "#2a1b3b",
          900: "#1d122a",
        },
        accent: {
          400: "#f0805c",
          500: "#e2623b",
          600: "#c24b28",
        },
      },
      fontFamily: {
        sans: ['"Avenir Next"', '"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
