import type { Config } from "tailwindcss";

// Bank of America concept demo theme: navy primary, red accent, Helvetica-style sans.
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
          50: "#f3f5f9",
          100: "#e3e8f2",
          200: "#c3cde2",
          300: "#95a6c8",
          400: "#5b74a6",
          500: "#2a4a85",
          600: "#0b2f6b",
          700: "#012169",
          800: "#011a52",
          900: "#00123b",
        },
        accent: {
          400: "#e8434f",
          500: "#dc1431",
          600: "#b30f28",
        },
      },
      fontFamily: {
        sans: ['"Helvetica Neue"', "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
