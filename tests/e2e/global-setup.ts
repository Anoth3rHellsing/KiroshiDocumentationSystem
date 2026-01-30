import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Global setup for Playwright tests...');
}

export default globalSetup;
