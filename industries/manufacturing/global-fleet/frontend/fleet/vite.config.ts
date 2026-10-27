import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
  preview: {
    proxy: {
      '/api': 'https://t-gf-after.demo.otterworks.app',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    reporters: ['default', 'junit'],
    outputFile: {
      junit: 'reports/vitest-junit.xml',
    },
  },
})
