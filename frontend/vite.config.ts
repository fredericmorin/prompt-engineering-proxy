import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
  server: {
    host: true,
    proxy: {
      "/api": process.env.BACKEND_URL ?? "http://localhost:8000",
      "/v1": process.env.BACKEND_URL ?? "http://localhost:8000",
      "/health": process.env.BACKEND_URL ?? "http://localhost:8000",
    },
  },
});
