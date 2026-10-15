import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8401,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8400" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    testTimeout: 15000,
  },
});
