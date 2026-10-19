import type { Config } from "tailwindcss";

// Wenlow theme: deep petrol primary, flat square corners,
// coral signal accent, system sans stack.
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
          50: "#eff6f7",
          100: "#d8eaed",
          200: "#b1d3d9",
          300: "#7fb3bd",
          400: "#4b8f9c",
          500: "#22707f",
          600: "#0e4a5a",
          700: "#0b3f4d",
          800: "#09343f",
          900: "#062831",
        },
        accent: {
          400: "#ea7d5f",
          500: "#e2603f",
          600: "#c24a2b",
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
