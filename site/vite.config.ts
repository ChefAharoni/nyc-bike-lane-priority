import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [svelte()],
  // maplibre-gl starts its worker from its own module URL; pre-bundling would move it and break the worker.
  test: { exclude: ['e2e/**', 'node_modules/**'] },
  optimizeDeps: { exclude: ['maplibre-gl'] },
})
