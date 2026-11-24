import type { Config } from "tailwindcss";
import clientApp from "../../../../frontend/client-app/tailwind.config";

// The client-app's Thistlecombe theme, unchanged; only the content globs are ours.
const config: Config = { ...clientApp, content: ["./index.html", "./src/**/*.{ts,tsx}"] };

export default config;
