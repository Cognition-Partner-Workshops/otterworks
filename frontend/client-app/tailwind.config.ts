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
          50: "#eef7f7",
          100: "#d5ecec",
          200: "#a9d6d7",
          300: "#74b9bc",
          400: "#3f9599",
          500: "#1f777c",
          600: "#0f5f66",
          700: "#0c4c52",
          800: "#0a3d42",
          900: "#072e32",
        },
        accent: {
          400: "#f5c043",
          500: "#eeab12",
          600: "#c98d07",
        },
      },
      fontFamily: {
        sans: ['"Inter"', '"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
