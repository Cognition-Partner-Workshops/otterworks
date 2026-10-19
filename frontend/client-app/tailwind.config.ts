import type { Config } from "tailwindcss";

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
          50: "#f3f7f5",
          100: "#e1ece7",
          200: "#c2d8ce",
          300: "#93bba9",
          400: "#5f9580",
          500: "#3a7560",
          600: "#1f5c48",
          700: "#1a4d3c",
          800: "#153e31",
          900: "#0f2f25",
        },
        accent: {
          400: "#f0a640",
          500: "#e08e1f",
          600: "#b97315",
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
