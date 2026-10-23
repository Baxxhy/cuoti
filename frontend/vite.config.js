import { defineConfig, loadEnv } from 'vite'
import { normalizeApiBase } from './src/utils/api-base.js'
import uni from '@dcloudio/vite-plugin-uni'
import UniComponents from '@uni-helper/vite-plugin-uni-components'
import { UniUIResolver } from '@uni-helper/vite-plugin-uni-components/resolvers'

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }
  if (process.env.UNI_PLATFORM === 'app' || process.env.UNI_PLATFORM === 'app-plus') {
    // A successful production build must have an explicit reachable HTTPS endpoint.
    if (mode === 'production') normalizeApiBase(env.VITE_API_BASE_URL)
  }
  const backend = env.ZHIWEI_BACKEND_URL || 'http://127.0.0.1:8002'
  return {
    plugins: [uni(), UniComponents({ resolvers: [UniUIResolver()] })],
    server: {
      host: '0.0.0.0',
      watch: {
        ignored: [
          '**/.playwright-libs/**',
          '**/.playwright-browsers/**',
          '**/test-results/**',
          '**/playwright-report/**',
          '**/dist/**',
        ],
      },
      proxy: {
        '/api': {
          target: backend,
          changeOrigin: true,
        },
        '/uploads': {
          target: backend,
          changeOrigin: true,
        },
        '/reports': {
          target: backend,
          changeOrigin: true,
        },
      },
    },
  }
})
