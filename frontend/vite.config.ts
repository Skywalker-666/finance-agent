import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE is "/<repo-name>/" when built for GitHub Pages, "/" locally.
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173 },
});
