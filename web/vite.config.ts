import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In development /api goes to a collector on :8000. Point HUB_API at the NAS
// (http://<nas>:8000) to work against live data instead.
const apiTarget = process.env.HUB_API ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Keep the browser's Host header: the collector checks that writes come
    // from the same origin (collector/app/security.py).
    proxy: { '/api': { target: apiTarget, changeOrigin: false } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
