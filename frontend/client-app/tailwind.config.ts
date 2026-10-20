import type { Config } from "tailwindcss";

// Pine-and-brass insurer theme with compact corners and a system sans stack.
const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "../../industries/insurance/mobile-claims/src/**/*.{ts,tsx}",
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
          50: "#f2f7f6",
          100: "#dcebe8",
          200: "#b5d5cf",
          300: "#84b8af",
          400: "#4f958a",
          500: "#2c766c",
          600: "#1d5c54",
          700: "#174a44",
          800: "#123b36",
          900: "#0d2c28",
        },
        accent: {
          400: "#d6a545",
          500: "#c08a2e",
          600: "#9c6f22",
        },
      },
      fontFamily: {
        sans: ['"Source Sans 3"', '"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
