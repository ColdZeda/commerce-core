import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 开发期把 /api 转给本机 Django；生产由 nginx 反代（plan §2.1）。
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
