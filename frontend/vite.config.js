import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 可选：把 /api 与 /ws 代理到后端，从而避免跨域。
    // 若启用代理，请把 src/api.js 里的 BASE 改成空字符串 ''。
    // proxy: {
    //   '/api': 'http://localhost:8000',
    //   '/ws': { target: 'ws://localhost:8000', ws: true },
    // },
  },
})
