import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to the FastAPI backend (uvicorn backend.api:app) on :8000.
// Set MOCK = true in src/api.ts to run the UI standalone without a backend.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
});
