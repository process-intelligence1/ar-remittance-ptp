/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// VITE_BASE: "/ar-remittance-ptp/live/" on GitHub Pages (live edition), "/" locally.
// VITE_API_URL: the API address of the live edition, set at build time from the repo variable API_BASE_URL (never committed).
// Local development: no VITE_API_URL, requests to /api go through the proxy to the API on this laptop.
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], css: false },
});
