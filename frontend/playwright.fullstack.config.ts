import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e-fullstack',
  fullyParallel: false, // Run fullstack flow scenarios sequentially to avoid state collisions
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // Deterministic single-worker execution against real backend
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 45000,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(process.env.CI ? {} : { channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge' }),
      },
    },
  ],
  webServer: process.env.CI
    ? {
        command: 'npm run dev -- --host 127.0.0.1 --port 5173',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: false,
        timeout: 120000,
      }
    : undefined,
});
