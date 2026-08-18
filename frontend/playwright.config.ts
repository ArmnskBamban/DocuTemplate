import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E configuration for PraktiKit frontend.
 * Tests the full upload → analyze → generate → download flow.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // Run tests serially (they share backend API)
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // Single worker to avoid backend session conflicts
  reporter: 'html',
  
  use: {
    baseURL: 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Start dev server before tests (assumes backend is already running)
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
