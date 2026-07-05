import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Proxy target: if VITE_API_URL is an absolute URL, use that as the
// proxy target. Otherwise the default proxy target is the local FastAPI
// dev server (port 8000). The proxy is only effective when adminApi
// uses a relative baseURL like `/api/v1` — see `src/lib/api.ts`.
const DEFAULT_PROXY_TARGET = 'http://localhost:8000'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL
  const proxyTarget = apiUrl && /^https?:\/\//.test(apiUrl)
    ? new URL(apiUrl).origin
    : DEFAULT_PROXY_TARGET

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          credentials: 'include', // Forward cookies from backend through proxy
        },
      },
    },
  }
})
