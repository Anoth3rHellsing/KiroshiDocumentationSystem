import { defineConfig, devices } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  testDir: path.resolve(__dirname, './tests/e2e'),
  timeout: 120_000,
  expect: {
    timeout: 60_000,
  },
  globalSetup: path.resolve(__dirname, './tests/e2e/global-setup.ts'),
  snapshotPathTemplate: '{testDir}/baselines/{projectName}/{arg}{ext}',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8501',
    trace: 'on-first-retry',
    navigationTimeout: 60_000,
    actionTimeout: 30_000,
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
