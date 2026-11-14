import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api calls go to the python server on port 8000
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  // three.js (the 3D walk) is already its own file that loads only when the 3D view is opened
  build: { chunkSizeWarningLimit: 700 },
});
