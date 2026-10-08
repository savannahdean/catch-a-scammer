// Vite dev server + build for the React client.
//
// In development the game runs on http://localhost:5173 and every API call is
// proxied to the FastAPI server (default http://127.0.0.1:8000), so the browser
// only ever talks to one origin and no CORS setup is needed. Point it somewhere
// else with:   API_URL=http://192.168.1.20:8000 npm run dev
//
// `npm run build` writes dist/, which the FastAPI server also serves at "/".
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API = process.env.API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': API,
      '/scenarios': API,
      '/health': API,
    },
  },
})
