import type { Config } from "tailwindcss";

// Public-sector theme with a statehouse green primary and seal gold accent.
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
          50: "#f2f6f5",
          100: "#e1ebe8",
          200: "#bfd4ce",
          300: "#93b5ab",
          400: "#5e8f82",
          500: "#3a6f62",
          600: "#1f5446",
          700: "#19463b",
          800: "#143830",
          900: "#0f2a24",
        },
        accent: {
          400: "#d4a64a",
          500: "#c08f2c",
          600: "#9c7221",
        },
      },
      fontFamily: {
        sans: ['"Public Sans"', '"Segoe UI"', "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
