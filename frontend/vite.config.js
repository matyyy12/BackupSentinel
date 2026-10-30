import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api/backups': {
          target: env.BACKUP_API_TARGET || 'http://127.0.0.1:8000',
        },
        '/api/alerts': {
          target: env.MONITORING_API_TARGET || 'http://127.0.0.1:8002',
        },
      },
    },
  }
})
