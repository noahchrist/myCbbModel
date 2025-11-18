import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import spa from 'vite-plugin-spa';

export default defineConfig({
  base: '/',
  plugins: [react(), spa()],
  build: {
    rollupOptions: {
      output: {
        // ensures single-page app fallback works
      }
    }
  }
})

