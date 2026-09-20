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
    hmr: {
      // Follow the port the page was opened on; hardcoding 80 broke hot reload
      // because the service is published on 8080 (finding L5).
      clientPort: Number(process.env.VITE_HMR_CLIENT_PORT) || undefined,
      timeout: 30000
    }
  },
  // Optimize dependency pre-bundling
  optimizeDeps: {
    exclude: ['vue']
  }
})
