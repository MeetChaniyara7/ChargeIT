import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The kiosk runs on its own port so it can sit next to the driver web app (5173) while developing.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5174 },
  preview: { port: 5174 },
})
