import { chromium, type FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // Add a very basic setup if it's missing, the error was "Cannot find module './tests/e2e/global-setup.ts'"
}

export default globalSetup;
