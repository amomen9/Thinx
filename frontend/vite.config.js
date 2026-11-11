import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 80,
    strictPort: true,
    watch: {
      usePolling: true,
      interval: 1000
    },
    // Without Docker (npm run dev), /api is forwarded to a locally running backend
    proxy: {
      '/api': process.env.VITE_DEV_API_PROXY || 'http://localhost:5000'
    },
    hmr: {
      // Behind Caddy the browser connects on 443 (D-S6); 80 when run without it
      clientPort: Number(process.env.VITE_HMR_CLIENT_PORT || 80),
      // Timeout for HMR connection
      timeout: 30000
    }
  },
  // Optimize dependency pre-bundling
  optimizeDeps: {
    exclude: ['vue']
  }
})
