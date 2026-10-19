import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    borderRadius: {
      none: "0",
      sm: "4px",
      DEFAULT: "6px",
      md: "8px",
      lg: "10px",
      xl: "14px",
      "2xl": "18px",
      "3xl": "24px",
      full: "9999px",
    },
    extend: {
      colors: {
        otter: {
          50: "#f2f7f3",
          100: "#e0ece3",
          200: "#c0d9c7",
          300: "#93bea0",
          400: "#5f9a71",
          500: "#3b7a4f",
          600: "#24603a",
          700: "#1d4e30",
          800: "#173e27",
          900: "#12311f",
        },
        accent: {
          400: "#e8774f",
          500: "#d95f33",
          600: "#b84a23",
        },
      },
      fontFamily: {
        sans: ['"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
