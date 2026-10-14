import type { Config } from "tailwindcss";

// Bank of America concept demo theme: navy, red accents, and the supplied font stack.
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
          50: "#f5f5f5",
          100: "#e9edf5",
          200: "#d2dbea",
          300: "#b1c1dc",
          400: "#819bc5",
          500: "#5276ae",
          600: "#2c5597",
          700: "#123b7d",
          800: "#012169",
          900: "#012169",
        },
        accent: {
          400: "#ed536c",
          500: "#e31837",
          600: "#c41230",
        },
        link: "#0052c2",
      },
      fontFamily: {
        sans: ["Roboto", "Arial", '"Helvetica Neue"', "Helvetica", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
