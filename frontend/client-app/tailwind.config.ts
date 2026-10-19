import type { Config } from "tailwindcss";

// Industrial theme: graphite primary, safety-orange accent, flat square corners.
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
          50: "#f3f5f6",
          100: "#e3e8eb",
          200: "#c4ced4",
          300: "#9aaab3",
          400: "#6b7f8a",
          500: "#4a5f6b",
          600: "#2f4550",
          700: "#263943",
          800: "#1d2c34",
          900: "#141f25",
        },
        accent: {
          400: "#f08a45",
          500: "#e0701f",
          600: "#b85a17",
        },
      },
      fontFamily: {
        sans: ["Roboto", '"Helvetica Neue"', "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
