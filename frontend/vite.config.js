import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During development the API runs on uvicorn at :8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
