import { defineConfig } from '@playwright/test';

/** Runs against the API-served production build (scripts/e2e.sh starts it on a throwaway database). Uses the installed Chrome. */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8011', channel: 'chrome', headless: true, viewport: { width: 1440, height: 900 }, trace: 'retain-on-failure' },
});
