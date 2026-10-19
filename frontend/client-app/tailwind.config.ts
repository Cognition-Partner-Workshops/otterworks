import type { Config } from "tailwindcss";

// Larkbridge Freight theme: teal primary, signal-orange accent, system sans stack.
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
          50: "#f2f7f6",
          100: "#dcebe8",
          200: "#b5d5cf",
          300: "#84b8af",
          400: "#4f958a",
          500: "#2a756b",
          600: "#165c54",
          700: "#114c46",
          800: "#0d3d38",
          900: "#0a2f2b",
        },
        accent: {
          400: "#f08a45",
          500: "#e5702a",
          600: "#c25a1c",
        },
      },
      fontFamily: {
        sans: ['"Inter"', '"Segoe UI"', "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
