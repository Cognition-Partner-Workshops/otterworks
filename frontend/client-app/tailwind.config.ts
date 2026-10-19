import type { Config } from "tailwindcss";

// Vetchline theme: deep indigo primary, teal accent, soft rounded corners,
// system UI sans stack.
const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    borderRadius: {
      none: "0",
      sm: "3px",
      DEFAULT: "6px",
      md: "6px",
      lg: "8px",
      xl: "10px",
      "2xl": "14px",
      "3xl": "18px",
      full: "9999px",
    },
    extend: {
      colors: {
        otter: {
          50: "#f5f4fb",
          100: "#e9e6f7",
          200: "#d0caee",
          300: "#ada3df",
          400: "#8475cb",
          500: "#5f4fb5",
          600: "#45369a",
          700: "#382c80",
          800: "#2c2366",
          900: "#211a4d",
        },
        accent: {
          400: "#17a394",
          500: "#0f8a7e",
          600: "#0b7067",
        },
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", '"Segoe UI"', "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
