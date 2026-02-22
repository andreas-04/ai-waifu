import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],

  server: {
    proxy: {
      // Forward all /api/* requests to the Flask backend on port 5001
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      // Forward /upload (screen capture frames for productivity classification)
      '/upload': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      // Forward /static/* so audio/assets served by Flask are reachable
      '/static': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
})
