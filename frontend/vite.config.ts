import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// En desarrollo, Vite (puerto 5173) reenvía las llamadas a la API de FastAPI (puerto 8000).
// En la demo, `npm run build` genera dist/ y FastAPI lo sirve en http://127.0.0.1:8000/app
const API = 'http://127.0.0.1:8000'

export default defineConfig({
  base: '/app/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/v1': API,
      '/pasarela': API,
      '/docs': API,
      '/openapi.json': API,
    },
  },
})
