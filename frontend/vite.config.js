import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/reset': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/session': 'http://localhost:8000',
    },
  },
})
