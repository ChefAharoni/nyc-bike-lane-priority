import { defineConfig } from '@playwright/test';

// Runs against the assembled real-data build (data_out -> site/dist) served by `vite preview`.
// The build uses `--mode test` so the map is exposed as window.__map. Needs data_out/ from a pipeline run.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: 0,
  use: { baseURL: 'http://localhost:4173', channel: 'chrome' },
  webServer: {
    command:
      'SITE_BUILD_ARGS="--mode test" ../scripts/assemble_site.sh ../data_out ../data_out/snapshots && npx vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: false,
    timeout: 300_000,
  },
});
