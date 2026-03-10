import { defineConfig } from 'vite';

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8010';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
