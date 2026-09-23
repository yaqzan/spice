import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev runs on 5181 and proxies /api to the Flask app on 5003. In production the
// Flask app serves this build itself, so everything is same-origin and the proxy
// never comes into it.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5181,
    host: '127.0.0.1',
    proxy: {
      '/api': { target: 'http://127.0.0.1:5003', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
