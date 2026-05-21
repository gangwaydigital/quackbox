import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    // Vite 5+ blocks requests whose Host header doesn't match an entry here.
    // We're a self-hosted app behind the user's router, so allow any hostname
    // — covers reverse proxies, .local mDNS names, dashboards like homepage,
    // and access from phones / other LAN devices.
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Pull large/cacheable vendors into their own chunks so the main
        // bundle stays small and they can be cached independently.
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-recharts': ['recharts'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
    // We're already chunking aggressively; raise the size warning so it doesn't
    // false-positive on the recharts chunk specifically (still ~300KB minified).
    chunkSizeWarningLimit: 350,
  },
})
