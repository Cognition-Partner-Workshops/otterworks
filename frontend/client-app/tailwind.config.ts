import type { Config } from "tailwindcss";

// Teal and coral palette with flat square corners and Source Sans 3.
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
          50: "#f2f7f7",
          100: "#dcebea",
          200: "#b5d6d4",
          300: "#84bab7",
          400: "#4f9894",
          500: "#2a7a76",
          600: "#146461",
          700: "#0f514f",
          800: "#0c4140",
          900: "#083130",
        },
        accent: {
          400: "#ef8a5f",
          500: "#e2703f",
          600: "#c2582b",
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
