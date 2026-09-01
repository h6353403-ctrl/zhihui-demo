import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ["localhost", "127.0.0.1", ".trycloudflare.com"],
    proxy: {
      // 前端只访问同源 /api，由 vite 转发到后端，不产生跨域
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
